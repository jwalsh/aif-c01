#!/usr/bin/env bb

(require '[babashka.curl :as curl])

(defn test-proxy []
  (try
    (let [response (curl/get "http://httpbin.org/ip"
                             {:proxy "http://localhost:3128"})]
      (println "Response status:" (:status response))
      (println "Body:" (:body response)))
    (catch Exception e
      (println "Error:" (.getMessage e)))))

(defn test-https-proxy []
  (try
    (let [response (curl/get "https://httpbin.org/ip"
                             {:proxy "http://localhost:3128"})]
      (println "Response status:" (:status response))
      (println "Body:" (:body response)))
    (catch Exception e
      (println "Error:" (.getMessage e)))))

;; Run the tests
(println "Testing HTTP proxy:")
(test-proxy)
(println "\nTesting HTTPS proxy:")
(test-https-proxy)
