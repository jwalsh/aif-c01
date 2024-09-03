(ns aif-c01.d2-generative-ai.concepts)

(def gen-ai-concepts
  {:prompt-engineering "Crafting effective inputs for AI models"
   :foundation-model "Large, general-purpose AI model"})

(defn explain-gen-ai-concept [concept]
  (get gen-ai-concepts concept "Concept not found"))

(defn list-gen-ai-use-cases []
  [:image-generation :text-generation :code-generation])
