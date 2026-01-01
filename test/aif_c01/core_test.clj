(ns aif-c01.core-test
  (:require [clojure.test :refer :all]
            [aif-c01.core :refer :all]))

(deftest a-test
  (testing "Core namespace loads successfully."
    (is (= 1 1))))
