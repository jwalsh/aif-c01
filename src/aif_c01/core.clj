(ns aif-c01.core
  (:require [aif-c01.d1.basics :as d1]
            [aif-c01.d2.gen-ai :as d2]
            [aif-c01.d3.foundation :as d3]
            [aif-c01.d4.responsible :as d4]
            [aif-c01.d5.security :as d5])
  (:gen-class))

(defn -main
  "Entry point for AWS Certified AI Practitioner (AIF-C01) exam preparation"
  [& args]
  (println "AWS Certified AI Practitioner (AIF-C01) Exam Prep Overview")

  (println "\nD1: Fundamentals of AI and ML")
  (println "AI explanation:" (d1/explain :ai))
  (println "ML types:" d1/ml-types)

  (println "\nD2: Fundamentals of Generative AI")
  (println "Embeddings:" (d2/explain :embeddings))
  (println "Use cases:" d2/use-cases)

  (println "\nD3: Applications of Foundation Models")
  (println "RAG:" (d3/describe-rag))
  (println "Eval metrics:" d3/eval-metrics)

  (println "\nD4: Guidelines for Responsible AI")
  (println "Features:" d4/features)
  (println "Dataset characteristics:" d4/dataset-chars)

  (println "\nD5: Security, Compliance, and Governance")
  (println "AWS security:" d5/aws-security)
  (println "Data governance:" d5/data-governance)

  (println "\nGood luck with your exam preparation!"))
