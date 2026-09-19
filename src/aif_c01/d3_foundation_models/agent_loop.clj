(ns aif-c01.d3-foundation-models.agent-loop
  "Bedrock agentic loop with tool use via converse API.

  Demonstrates the core agent pattern: send messages -> check stop reason ->
  execute tools -> feed results back -> repeat. Uses cognitect.aws for
  Bedrock Runtime interaction.

  Ported from aws-samples/sample-agentic-ai-demos."
  (:require [clojure.data.json :as json]
            [clojure.string :as str]
            [cognitect.aws.client.api :as aws]))

;; ---------------------------------------------------------------------------
;; Tool registry
;; ---------------------------------------------------------------------------

(defn make-tool-registry
  "Create an empty tool registry."
  []
  {:tools {}
   :schemas {}})

(defn register-tool
  "Register a tool with its handler function and schema."
  [registry tool-name handler description parameters]
  (-> registry
      (assoc-in [:tools tool-name] handler)
      (assoc-in [:schemas tool-name]
                {:name tool-name
                 :description description
                 :parameters parameters})))

(defn registry->bedrock-config
  "Convert tool registry to Bedrock toolConfig format."
  [registry]
  {:tools
   (mapv (fn [[_ schema]]
           {:toolSpec
            {:name (:name schema)
             :description (:description schema)
             :inputSchema
             {:json {:type "object"
                     :properties (:parameters schema)}}}})
         (:schemas registry))})

;; ---------------------------------------------------------------------------
;; Example tools
;; ---------------------------------------------------------------------------

(def weather-data
  {"seattle"  "62F, cloudy"
   "new york" "75F, sunny"
   "london"   "55F, rainy"
   "tokyo"    "80F, humid"})

(defn tool-get-weather
  "Get current weather for a city (stub)."
  [{:keys [city]}]
  (get weather-data (str/lower-case city)
       (str "No weather data for " city)))

;; The model sends infix text ("42 * 17"), so the expression is parsed directly
;; rather than passed to read-string/eval: read-string returns only the first
;; form (42), and eval would execute whatever the model sent.

(declare parse-sum)

(defn- parse-number
  "Read a numeric token as a long, or a double when it has a decimal point."
  [token]
  (if (str/includes? token ".")
    (Double/parseDouble token)
    (Long/parseLong token)))

(defn- parse-atom
  "Parse a number, a unary minus, or a parenthesised expression.
  Returns [value remaining-tokens]."
  [[token & more :as tokens]]
  (cond
    (nil? token) (throw (ex-info "Unexpected end of expression" {:tokens tokens}))
    (= "-" token) (let [[value remaining] (parse-atom more)]
                    [(- value) remaining])
    (= "(" token) (let [[value remaining] (parse-sum more)]
                    (if (= ")" (first remaining))
                      [value (next remaining)]
                      (throw (ex-info "Unbalanced parentheses" {:tokens tokens}))))
    :else [(parse-number token) more]))

(defn- parse-binary
  "Parse a left-associative run of `ops` over operands from `parse-operand`."
  [ops parse-operand tokens]
  (loop [[value remaining] (parse-operand tokens)]
    (if-let [op (ops (first remaining))]
      (let [[right after] (parse-operand (next remaining))]
        (recur [(op value right) after]))
      [value remaining])))

(defn- parse-product
  [tokens]
  (parse-binary {"*" * "/" /} parse-atom tokens))

(defn- parse-sum
  [tokens]
  (parse-binary {"+" + "-" -} parse-product tokens))

(defn tool-calculate
  "Evaluate a simple infix arithmetic expression over + - * / and parentheses."
  [{:keys [expression]}]
  (if-not (re-matches #"[\d+\-*/.()\s]+" (str expression))
    "Error: expression contains invalid characters"
    (try
      (let [[value remaining] (parse-sum (re-seq #"\d+\.?\d*|[+\-*/()]" expression))]
        (if (seq remaining)
          (str "Error: could not parse expression: " expression)
          (str value)))
      (catch ArithmeticException e
        (str "Error: " (.getMessage e)))
      (catch Exception _
        (str "Error: could not parse expression: " expression)))))

;; ---------------------------------------------------------------------------
;; Agent loop
;; ---------------------------------------------------------------------------

(defn make-bedrock-client
  "Create a Bedrock Runtime client."
  [region]
  (aws/client {:api :bedrock-runtime
               :region region}))

(defn extract-text
  "Extract text content from a Bedrock message."
  [message]
  (->> (:content message)
       (filter :text)
       (map :text)
       (str/join "\n")))

(defn execute-tools
  "Execute all tool_use blocks in an assistant message."
  [registry assistant-message]
  (let [tool-blocks (filter :toolUse (:content assistant-message))]
    (mapv (fn [block]
            (let [{:keys [name input toolUseId]} (:toolUse block)
                  handler (get-in registry [:tools name])]
              (if handler
                {:toolResult
                 {:toolUseId toolUseId
                  :content [{:text (str (handler input))}]}}
                {:toolResult
                 {:toolUseId toolUseId
                  :content [{:text (str "Error: unknown tool " name)}]
                  :status "error"}})))
          tool-blocks)))

(defn converse
  "Send a converse request to Bedrock."
  [client model-id messages system-prompt tool-config]
  (let [request (cond-> {:modelId model-id
                         :messages messages
                         :inferenceConfig {:temperature 0.0
                                           :maxTokens 4096}}
                  (seq system-prompt) (assoc :system [{:text system-prompt}])
                  (seq (:tools tool-config)) (assoc :toolConfig tool-config))]
    (aws/invoke client {:op :Converse :request request})))

(defn run-agent-loop
  "Execute the agent loop: converse -> tool use -> converse -> ... -> end_turn.

  Returns the final text response from the model."
  [{:keys [client model-id system-prompt registry max-iterations]
    :or {max-iterations 10}}
   user-input]
  (loop [messages [{:role "user" :content [{:text user-input}]}]
         iteration 0]
    (when (< iteration max-iterations)
      (let [tool-config (registry->bedrock-config registry)
            response (converse client model-id messages system-prompt tool-config)
            stop-reason (:stopReason response)
            assistant-message (get-in response [:output :message])
            messages (conj messages assistant-message)]
        (cond
          ;; Model is done
          (contains? #{"end_turn" "stop_sequence"} stop-reason)
          (extract-text assistant-message)

          ;; Model wants to use tools
          (= "tool_use" stop-reason)
          (let [tool-results (execute-tools registry assistant-message)
                messages (conj messages {:role "user" :content tool-results})]
            (recur messages (inc iteration)))

          ;; Max tokens — ask for continuation
          (= "max_tokens" stop-reason)
          (let [messages (conj messages {:role "user"
                                         :content [{:text "Continue."}]})]
            (recur messages (inc iteration)))

          :else
          (extract-text assistant-message))))))

;; ---------------------------------------------------------------------------
;; Convenience constructors
;; ---------------------------------------------------------------------------

(defn make-demo-agent
  "Create an agent with example tools for demonstration."
  ([] (make-demo-agent "us-east-1" "us.anthropic.claude-3-haiku-20240307-v1:0"))
  ([region model-id]
   (let [registry (-> (make-tool-registry)
                      (register-tool
                       "get_weather" tool-get-weather
                       "Get current weather for a city"
                       {:city {:type "string" :description "City name"}})
                      (register-tool
                       "calculate" tool-calculate
                       "Evaluate a mathematical expression"
                       {:expression {:type "string"
                                     :description "Math expression"}}))]
     {:client (make-bedrock-client region)
      :model-id model-id
      :system-prompt "You are a helpful assistant with access to tools."
      :registry registry
      :max-iterations 10})))

(comment
  ;; REPL usage:
  ;; (def agent (make-demo-agent))
  ;; (run-agent-loop agent "What is the weather in Seattle and what is 42 * 17?")
  )
