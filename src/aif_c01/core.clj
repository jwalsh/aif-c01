(ns aif-c01.core
  (:require [aif-c01.d1-fundamentals.basics :as d1]
            [aif-c01.d2-generative-ai.concepts :as d2]
            [aif-c01.d3-foundation-models.applications :as d3]
            [aif-c01.d4-responsible-ai.practices :as d4]
            [aif-c01.d5-security-compliance.governance :as d5])
  (:gen-class))

(defn -main
  "Entry point for AWS Certified AI Practitioner (AIF-C01) exam preparation"
  [& args]
  (println "AWS Certified AI Practitioner (AIF-C01) Exam Prep Overview")

  (println "\nD1: Fundamentals of AI and ML")
  (println "AI explanation:" (d1/explain-ai-term :ai))
  (println "ML types:" (d1/list-ml-types))

  (println "\nD2: Fundamentals of Generative AI")
  (println "Foundation model:" (d2/explain-gen-ai-concept :foundation-model))
  (println "Use cases:" (d2/list-gen-ai-use-cases))

  (println "\nD3: Applications of Foundation Models")
  (println "RAG:" (d3/describe-rag))
  (println "Model criteria:" (d3/list-model-selection-criteria))

  (println "\nD4: Guidelines for Responsible AI")
  (println "Features:" (d4/list-responsible-ai-features))
  (println "Bias effects:" (d4/describe-bias-effects))

  (println "\nD5: Security, Compliance, and Governance")
  (println "AWS security:" (d5/list-aws-security-services))
  (println "Data governance:" (d5/describe-data-governance-strategies))

  (println "\nGood luck with your exam preparation!"))
