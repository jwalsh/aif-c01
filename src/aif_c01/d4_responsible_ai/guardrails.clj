(ns aif-c01.d4-responsible-ai.guardrails
  "Neurosymbolic guardrails for agent tool validation.

  Symbolic rules intercept tool calls before execution, enforcing constraints
  the LLM cannot bypass. Implements the pattern from
  aws-samples/sample-why-agents-fail.

  Maps to AIF-C01 Domain 4: Guidelines for Responsible AI."
  (:require [clojure.data.json :as json]
            [clojure.string :as str]))

;; ---------------------------------------------------------------------------
;; Rule engine
;; ---------------------------------------------------------------------------

(defn make-rule
  "Create a guardrail rule.
   - condition-fn takes a context map and returns true if rule passes.
   - severity is :block, :warn, or :log."
  [rule-name condition-fn message & {:keys [severity] :or {severity :block}}]
  {:name rule-name
   :condition condition-fn
   :message message
   :severity severity})

(defn validate-rules
  "Evaluate rules against context. Returns [passed? violations]."
  [rules context]
  (let [violations (reduce
                    (fn [acc rule]
                      (try
                        (if ((:condition rule) context)
                          acc
                          (conj acc (str "[" (name (:severity rule)) "] "
                                         (:name rule) ": " (:message rule))))
                        (catch Exception e
                          (conj acc (str "[error] " (:name rule)
                                         ": rule evaluation failed: " (.getMessage e))))))
                    []
                    rules)]
    [(empty? violations) violations]))

;; ---------------------------------------------------------------------------
;; Guardrail engine
;; ---------------------------------------------------------------------------

(defn make-engine
  "Create a guardrail engine with empty rulesets."
  []
  {:rulesets {}
   :global-rules []
   :audit-log (atom [])})

(defn add-ruleset
  "Add a tool-specific ruleset to the engine."
  [engine tool-name rules]
  (assoc-in engine [:rulesets tool-name] rules))

(defn add-global-rule
  "Add a rule that applies to all tool calls."
  [engine rule]
  (update engine :global-rules conj rule))

(defn validate-tool-call
  "Check a tool call against all applicable rules.
   Returns {:tool-name :allowed :violations :context}."
  [engine tool-name tool-input]
  (let [context (assoc tool-input :tool-name tool-name)
        context-json (json/write-str context)
        global-rules (:global-rules engine)
        tool-rules (get-in engine [:rulesets tool-name] [])
        all-rules (concat global-rules tool-rules)
        [_ violations] (validate-rules all-rules context)
        blocking? (some #(str/starts-with? % "[block]") violations)
        result {:tool-name tool-name
                :allowed (not blocking?)
                :violations violations
                :context context}]
    (swap! (:audit-log engine) conj result)
    result))

;; ---------------------------------------------------------------------------
;; AWS Responsible AI pillar rules
;; ---------------------------------------------------------------------------

(def protected-terms
  #{"race" "ethnicity" "gender" "religion"})

(def pii-terms
  #{"ssn" "social security" "credit card" "passport number"})

(def destructive-tools
  #{"delete_all" "drop_table" "format_disk"})

(defn contains-term?
  "Check if any term appears in the JSON-serialized context."
  [terms context]
  (let [context-str (str/lower-case (json/write-str context))]
    (some #(str/includes? context-str %) terms)))

(defn build-responsible-ai-rules
  "Build global rules aligned to the eight AWS responsible AI pillars."
  []
  [(make-rule
    "no_demographic_targeting"
    (fn [ctx] (not (contains-term? protected-terms ctx)))
    "Input references protected demographic attributes"
    :severity :block)

   (make-rule
    "no_pii_in_input"
    (fn [ctx] (not (contains-term? pii-terms ctx)))
    "Input contains potential PII patterns"
    :severity :block)

   (make-rule
    "no_destructive_operations"
    (fn [ctx] (not (destructive-tools (:tool-name ctx))))
    "Destructive operation blocked by safety guardrail"
    :severity :block)

   (make-rule
    "rate_limit"
    (let [counts (atom {})]
      (fn [ctx]
        (let [tool-name (:tool-name ctx)
              current (swap! counts update tool-name (fnil inc 0))]
          (<= (get current tool-name) 50))))
    "Tool call rate limit exceeded (max 50 per session)"
    :severity :warn)])

;; ---------------------------------------------------------------------------
;; Example domain rules
;; ---------------------------------------------------------------------------

(def booking-rules
  [(make-rule "max_guests"
              #(<= (get % :guests 1) 10)
              "Maximum 10 guests per booking")
   (make-rule "max_nights"
              #(<= (get % :nights 1) 30)
              "Maximum 30 nights per booking")
   (make-rule "positive_guests"
              #(pos? (get % :guests 1))
              "Guest count must be positive")])

(def data-access-rules
  [(make-rule "limit_result_size"
              #(<= (get % :limit 100) 1000)
              "Query result limit cannot exceed 1000 rows")
   (make-rule "no_select_star"
              #(not (str/includes? (str/lower-case (get % :query "")) "select *"))
              "SELECT * queries are not permitted")])

;; ---------------------------------------------------------------------------
;; Responsible AI pillars reference
;; ---------------------------------------------------------------------------

(def responsible-ai-pillars
  [{:pillar "Fairness"
    :description "Equitable treatment across demographic groups"}
   {:pillar "Explainability"
    :description "Understandable model decisions and outputs"}
   {:pillar "Privacy & Security"
    :description "Protection of sensitive data and PII"}
   {:pillar "Transparency"
    :description "Clear disclosure of AI system capabilities and limits"}
   {:pillar "Veracity & Robustness"
    :description "Accurate and reliable model outputs"}
   {:pillar "Safety"
    :description "Prevention of harmful outcomes"}
   {:pillar "Controllability"
    :description "Human oversight and intervention capability"}
   {:pillar "Governance"
    :description "Organizational policies and accountability structures"}])

;; ---------------------------------------------------------------------------
;; Convenience
;; ---------------------------------------------------------------------------

(defn make-demo-engine
  "Create a guardrail engine with responsible AI and example domain rules."
  []
  (let [engine (reduce add-global-rule
                       (make-engine)
                       (build-responsible-ai-rules))]
    (-> engine
        (add-ruleset "book_hotel" booking-rules)
        (add-ruleset "query_data" data-access-rules))))

(comment
  ;; REPL usage:
  (def engine (make-demo-engine))

  ;; Should pass
  (validate-tool-call engine "book_hotel"
                      {:hotel "Grand Plaza" :guests 5 :nights 3})

  ;; Should block — too many guests
  (validate-tool-call engine "book_hotel"
                      {:hotel "Grand Plaza" :guests 15 :nights 3})

  ;; Should block — destructive operation
  (validate-tool-call engine "delete_all" {:target "users"})

  ;; Should block — PII detected
  (validate-tool-call engine "book_hotel"
                      {:hotel "Grand Plaza" :guests 2
                       :notes "send to SSN 123-45-6789"})

  ;; Audit log
  @(:audit-log engine))
