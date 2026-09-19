(ns aif-c01.d3-foundation-models.agent-loop-test
  "Offline tests for the agent loop: tool handlers and registry wiring.

  Everything here runs without AWS credentials or network access — the
  Bedrock-facing functions are exercised separately, by hand, against a real
  account."
  (:require [clojure.test :refer [deftest testing is]]
            [aif-c01.d3-foundation-models.agent-loop :as agent]))

(deftest tool-calculate-arithmetic
  (testing "evaluates the whole infix expression, not just the first form"
    ;; Regression: read-string returned 42 for "42 * 17".
    (is (= "714" (agent/tool-calculate {:expression "42 * 17"}))))

  (testing "honours operator precedence and parentheses"
    (is (= "14" (agent/tool-calculate {:expression "2 + 3 * 4"})))
    (is (= "20" (agent/tool-calculate {:expression "(2 + 3) * 4"}))))

  (testing "is left-associative"
    (is (= "75" (agent/tool-calculate {:expression "100 - 20 - 5"}))))

  (testing "handles unary minus and decimals"
    (is (= "-3" (agent/tool-calculate {:expression "-5 + 2"})))
    (is (= "3.0" (agent/tool-calculate {:expression "1.5 * 2"})))))

(deftest tool-calculate-rejects-bad-input
  (testing "rejects anything outside the arithmetic character set"
    (is (= "Error: expression contains invalid characters"
           (agent/tool-calculate {:expression "(System/exit 1)"})))
    (is (= "Error: expression contains invalid characters"
           (agent/tool-calculate {:expression "rm -rf"}))))

  (testing "reports unbalanced parentheses rather than throwing"
    (is (= "Error: could not parse expression: (1 + 2"
           (agent/tool-calculate {:expression "(1 + 2"}))))

  (testing "reports division by zero rather than throwing"
    (is (= "Error: Divide by zero"
           (agent/tool-calculate {:expression "8 / 0"})))))

(deftest tool-get-weather-stub
  (testing "looks up known cities case-insensitively"
    (is (= "62F, cloudy" (agent/tool-get-weather {:city "Seattle"}))))

  (testing "falls back to a message for unknown cities"
    (is (= "No weather data for Paris"
           (agent/tool-get-weather {:city "Paris"})))))

(deftest demo-agent-registry
  (let [{:keys [registry model-id max-iterations]} (agent/make-demo-agent)]
    (testing "registers both demo tools"
      (is (= #{"get_weather" "calculate"} (set (keys (:tools registry))))))

    (testing "carries the loop configuration the agent needs"
      (is (string? model-id))
      (is (pos? max-iterations)))

    (testing "converts the registry into a Bedrock toolConfig"
      (is (= 2 (count (:tools (agent/registry->bedrock-config registry))))))))

(deftest extract-text-joins-text-blocks
  (testing "concatenates text blocks and ignores non-text content"
    (is (= "a\nb"
           (agent/extract-text {:content [{:text "a"}
                                          {:toolUse {:name "calculate"}}
                                          {:text "b"}]})))))
