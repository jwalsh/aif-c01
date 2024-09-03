(ns aif-c01.d1-fundamentals.basics)

(def ai-ml-terms
  {:ai "Artificial Intelligence"
   :ml "Machine Learning"
   :dl "Deep Learning"})

(defn explain-ai-term [term]
  (get ai-ml-terms term "Term not found"))

(defn list-ml-types []
  [:supervised :unsupervised :reinforcement])
