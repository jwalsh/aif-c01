(ns user
  (:require [rebel-readline.core :as rebel]
            [rebel-readline.clojure.line-reader :as clj-line-reader]
            [rebel-readline.clojure.service.local :as clj-service]
            [rebel-readline.clojure.main :as rebel-main]
            [clojure.main :as main]
            [portal.api :as p]
            [cognitect.aws.client.api :as aws]))

(defn help []
  (println "Available commands:")
  (println "  (help)    - Show this help message")
  (println "  (portal)  - Open a new Portal instance")
  (println "  (tap> x)  - Send data to Portal")
  (println "  (doc x)   - Show documentation for x")
  (println "  (source x) - Show source code for x")
  (println "  (aws-info) - Show current AWS configuration"))

(defn portal []
  (let [p (p/open)]
    (add-tap #'p/submit)
    (println "Portal opened. Use (tap> x) to send data to Portal.")
    p))

(defn parse-endpoint
  "Parse an endpoint URL into a cognitect.aws endpoint-override map."
  [url]
  (let [uri (java.net.URI. url)]
    {:protocol (keyword (.getScheme uri))
     :hostname (.getHost uri)
     :port     (.getPort uri)}))

(defn aws-info []
  (println "Current AWS configuration:")
  (println "Region:" (System/getProperty "aws.region"))
  (println "Endpoint override:" (or (System/getenv "AWS_ENDPOINT_URL")
                                    (System/getenv "LOCALSTACK_ENDPOINT")))
  (println "AWS Profile:" (or (System/getenv "AWS_PROFILE") "default")))

(defn make-aws-client
  "Create a cognitect.aws client, using LocalStack endpoint when configured."
  [service-kw]
  (let [endpoint-url (or (System/getenv "AWS_ENDPOINT_URL")
                         (System/getenv "LOCALSTACK_ENDPOINT"))]
    (aws/client
     (if endpoint-url
       {:api service-kw
        :endpoint-override (parse-endpoint endpoint-url)}
       {:api service-kw}))))

(defn configure-aws []
  (let [endpoint-url (or (System/getenv "AWS_ENDPOINT_URL")
                         (System/getenv "LOCALSTACK_ENDPOINT"))]
    (when endpoint-url
      (println "AWS client configured with endpoint:" endpoint-url))))

(defn rebel-repl []
  (configure-aws)
  (rebel/with-line-reader
    (clj-line-reader/create
     (clj-service/create))
    (main/repl
     :prompt (fn []) ; prompt is handled by line-reader
     :read (rebel-main/create-repl-read)
     :init #(do
              (println "Welcome to the AIF-C01 REPL with rebel-readline!")
              (println "Type (help) for available commands.")
              (aws-info)
              (portal)))))

(defn -main [& args]
  (rebel-repl))
