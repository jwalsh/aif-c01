(ns aif-c01.d0-setup.environment
  (:require [cognitect.aws.client.api :as aws]
            [cognitect.aws.credentials :as credentials]))

(defn test-proxy []
  (try
    (let [response (client/get "http://httpbin.org/ip"
                               {:proxy-host "localhost"
                                :proxy-port 3128})]
      {:status :success
       :message "Proxy test successful"
       :body (:body response)})
    (catch Exception e
      {:status :error
       :message (str "Proxy test failed: " (.getMessage e))})))

(defn check-proxy []
  (println "Testing proxy configuration...")
  (let [result (test-proxy)]
    (println (if (= (:status result) :success) "✅" "❌") (:message result))
    (when (= (:status result) :success)
      (println "Response body:" (:body result)))
    result))

;; Add this to your existing check-environment function
(defn check-environment []
  (println "Checking AWS environment and services...")
  (let [results (assoc (run-all-checks)
                       :proxy (check-proxy))]
    (display-check-results results)
    results))

(defn check-aws-credentials []
  (try
    (let [creds (credentials/default-credentials-provider)]
      (if-let [aws-creds (credentials/credentials creds)]
        {:status :success :message "AWS credentials found" :credentials aws-creds}
        {:status :error :message "No AWS credentials found"}))
    (catch Exception e
      {:status :error :message (str "Error checking AWS credentials: " (.getMessage e))})))

(defn check-sagemaker-connection []
  (let [sm-client (aws/client {:api :sagemaker})]
    (try
      (aws/invoke sm-client {:op :ListNotebookInstances})
      {:status :success :message "Successfully connected to SageMaker"}
      (catch Exception e
        {:status :error :message (str "Error connecting to SageMaker: " (.getMessage e))}))))

(defn check-bedrock-connection []
  (let [bedrock-client (aws/client {:api :bedrock})]
    (try
      (aws/invoke bedrock-client {:op :ListFoundationModels})
      {:status :success :message "Successfully connected to Bedrock"}
      (catch Exception e
        {:status :error :message (str "Error connecting to Bedrock: " (.getMessage e))}))))

(defn check-partyrock-connection []
  ;; As of now, there's no direct API for PartyRock. We'll simulate a check.
  {:status :info :message "PartyRock connection check is not available via API. Please check manually at https://partyrock.aws/"})

(defn check-amazon-q-connection []
  ;; As of now, there's no direct API for Amazon Q. We'll simulate a check.
  {:status :info :message "Amazon Q connection check is not available via API. Please verify access through the AWS Console."})

(defn run-all-checks []
  {:aws-credentials (check-aws-credentials)
   :sagemaker (check-sagemaker-connection)
   :bedrock (check-bedrock-connection)
   :partyrock (check-partyrock-connection)
   :amazon-q (check-amazon-q-connection)})

(defn display-check-results [results]
  (doseq [[service result] results]
    (println (str (name service) ":")
             (case (:status result)
               :success "✅"
               :error "❌"
               :info "ℹ️")
             (:message result))
    (when (= service :aws-credentials)
      (when-let [creds (:credentials result)]
        (println "  Access Key ID:" (subs (:access-key-id creds) 0 5) "..."
                 "\n  Expiration:" (:expiration creds))))))

(defn check-environment []
  (println "Checking AWS environment and services...")
  (let [results (run-all-checks)]
    (display-check-results results)
    results))
