(ns aif-c01.namespaces-test
  "Guards against exercise namespaces that no longer compile.

  The D0 and D3 namespaces were both broken at one point without any test
  noticing, because nothing required them."
  (:require [clojure.test :refer [deftest testing is]]))

(def exercise-namespaces
  '[aif-c01.core
    aif-c01.d0-setup.environment
    aif-c01.d1-fundamentals.basics
    aif-c01.d2-generative-ai.concepts
    aif-c01.d3-foundation-models.applications
    aif-c01.d3-foundation-models.agent-loop
    aif-c01.d4-responsible-ai.practices
    aif-c01.d4-responsible-ai.guardrails
    aif-c01.d5-security-compliance.governance])

(deftest every-exercise-namespace-loads
  (doseq [ns-sym exercise-namespaces]
    (testing (str ns-sym)
      (is (nil? (require ns-sym :reload))
          (str ns-sym " failed to load")))))
