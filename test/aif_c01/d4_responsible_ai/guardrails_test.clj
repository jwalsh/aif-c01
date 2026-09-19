(ns aif-c01.d4-responsible-ai.guardrails-test
  "Offline tests for the guardrail engine used in the D4 exercises."
  (:require [clojure.test :refer [deftest testing is]]
            [aif-c01.d4-responsible-ai.guardrails :as guardrails]))

(defn- validate
  [tool-name args]
  (guardrails/validate-tool-call (guardrails/make-demo-engine) tool-name args))

(deftest allows-conforming-calls
  (testing "a booking within limits passes with no violations"
    (let [result (validate "book_hotel" {:hotel "Grand Plaza" :guests 5 :nights 3})]
      (is (true? (:allowed result)))
      (is (empty? (:violations result))))))

(deftest blocks-domain-rule-violations
  (testing "a booking over the guest limit is blocked"
    (let [result (validate "book_hotel" {:hotel "Grand Plaza" :guests 15 :nights 3})]
      (is (false? (:allowed result)))
      (is (seq (:violations result))))))

(deftest blocks-destructive-tools
  (testing "destructive operations are blocked by the global safety rule"
    (let [result (validate "delete_all" {:target "users"})]
      (is (false? (:allowed result)))
      (is (seq (:violations result))))))

(deftest blocks-pii-in-input
  (testing "an SSN in a free-text field is blocked"
    (let [result (validate "book_hotel" {:hotel "Grand Plaza"
                                         :guests 2
                                         :notes "send to SSN 123-45-6789"})]
      (is (false? (:allowed result)))
      (is (seq (:violations result))))))

(deftest records-an-audit-entry-per-call
  (testing "every decision is appended to the audit log"
    (let [engine (guardrails/make-demo-engine)]
      (guardrails/validate-tool-call engine "book_hotel" {:hotel "X" :guests 2 :nights 1})
      (guardrails/validate-tool-call engine "delete_all" {:target "users"})
      (is (= 2 (count @(:audit-log engine)))))))
