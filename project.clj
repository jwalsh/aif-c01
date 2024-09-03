(defproject aif-c01 "0.1.0-SNAPSHOT"
  :description "AWS Certified AI Practitioner (AIF-C01) exam preparation"
  :url "https://github.com/jwalsh/aif-c01"
  :license {:name "MIT"
            :url "https://opensource.org/licenses/MIT"}
  :dependencies [[org.clojure/clojure "1.11.1"]
                 [com.bhauman/rebel-readline "0.1.4"]
                 [djblue/portal "0.45.0"]
                 [amazonica "0.3.164"]
                 [com.cognitect.aws/api "0.8.686"]
                 [com.cognitect.aws/endpoints "1.1.12.489"]
                 [com.cognitect.aws/s3 "848.2.1413.0"]
                 [com.cognitect.aws/glue "848.2.1413.0"]
                 [com.cognitect.aws/sagemaker "848.2.1413.0"]
                 [com.cognitect.aws/bedrock "869.2.1616.0"]
                 [com.cognitect.aws/lambda "848.2.1413.0"]
                 ;;                 [com.cognitect.aws/cloudwatch "848.2.1413.0"]
                 ;;                 [com.cognitect.aws/comprehend "848.2.1413.0"]
                 ;;                 [com.cognitect.aws/lex "848.2.1413.0"]
                 [com.cognitect.aws/kendra "848.2.1413.0"]
                 ;;                 [com.cognitect.aws/personalize "848.2.1413.0"]
                 [com.cognitect.aws/dynamodb "848.2.1413.0"]
                 ;;                 [com.cognitect.aws/opensearch "848.2.1413.0"]
                 [org.clojure/data.json "2.4.0"]
                 [clj-http "3.12.3"]]
  :main ^:skip-aot aif-c01.core
  :target-path "target/%s"
  :plugins [[lein-cljfmt "0.9.2"]
            [lein-kibit "0.1.8"]
            [jonase/eastwood "1.4.0"]]
  :profiles {:uberjar {:aot :all
                       :jvm-opts ["-Dclojure.compiler.direct-linking=true"]}
             :dev {:source-paths ["src" "dev"]
                   :dependencies [[org.clojure/tools.namespace "1.4.4"]]
                   :repl-options {:init-ns user
                                  :init (do
                                          (println "Welcome to the AIF-C01 REPL!")
                                          (println "Type (help) for a list of commands.")
                                          (require '[portal.api :as p])
                                          (def portal (p/open))
                                          (add-tap #'p/submit))
                                  :prompt (fn [ns] (str "🚀 " ns "=> "))}}
             :lcl {:dependencies [[org.testcontainers/localstack "1.17.3"]]
                   :jvm-opts ["-Daws.region=us-east-1"
                              "-Daws.accessKeyId=test"
                              "-Daws.secretKey=test"]
                   :env {:endpoint-override "http://localhost:4566"}}
             :dev-aws {:jvm-opts ["-Daws.region=us-east-1"]
                       :env {:aws-profile "dev"}}}
  :aliases {"lint" ["do" ["kibit"] ["eastwood"] ["cljfmt" "check"]]
            "lint-fix" ["do" ["kibit" "--replace"] ["cljfmt" "fix"]]
            "portal" ["run" "-m" "portal.main"]
            "rebel" ["trampoline" "run" "-m" "user"]})
