;;; aws-ai-practice.el --- Support for AWS AI Fundamentals practice questions

;;; Commentary:
;; This module provides support for practicing AWS AI Fundamentals questions
;; in org-mode files.

;;; Code:

(require 'org)

(defvar-local aws-ai-practice-hide-properties t
  "Whether to hide property drawers in AWS AI practice files.")

(defun aws-ai-practice-toggle-property-visibility ()
  "Toggle visibility of property drawers in the current buffer."
  (interactive)
  (setq aws-ai-practice-hide-properties (not aws-ai-practice-hide-properties))
  (aws-ai-practice-update-property-visibility)
  (message "Property drawers are now %s" 
           (if aws-ai-practice-hide-properties "hidden" "visible")))

(defun aws-ai-practice-update-property-visibility ()
  "Update visibility of property drawers based on current setting."
  (save-excursion
    (goto-char (point-min))
    (while (re-search-forward "^[ \t]*:PROPERTIES:" nil t)
      (let ((drawer-begin (match-beginning 0))
            (drawer-end (save-excursion
                          (re-search-forward "^[ \t]*:END:" nil t)
                          (point))))
        (when drawer-end
          (outline-flag-region drawer-begin drawer-end aws-ai-practice-hide-properties))))))

(defun aws-ai-practice-set-answer (index)
  "Set the answer for the current question to the option at INDEX."
  (interactive "nEnter the answer number (1-4): ")
  (save-excursion
    (org-back-to-heading t)
    (let ((options (org-entry-get-multivalued-property nil "ITEM")))
      (when (and (>= index 1) (<= index (length options)))
        (dotimes (i (length options))
          (setf (nth i options) (replace-regexp-in-string "\\[[ X]\\]" "[ ]" (nth i options))))
        (setf (nth (1- index) options) (replace-regexp-in-string "\\[ \\]" "[X]" (nth (1- index) options)))
        (org-entry-put-multivalued-property nil "ITEM" options)))))

(defun aws-ai-practice-check-answer ()
  "Check the answer for the current question and provide feedback."
  (interactive)
  (save-excursion
    (org-back-to-heading t)
    (let* ((correct-answer (org-entry-get nil "ANSWER"))
           (explanation (org-entry-get nil "EXPLANATION"))
           (options (org-entry-get-multivalued-property nil "ITEM"))
           (selected (cl-position "[X]" options :test 'string-match))
           (correct (cl-position correct-answer options :test 'string=)))
      (org-entry-put nil "LAST_ANSWERED" (format-time-string "%Y-%m-%d %H:%M:%S"))
      (if (eq selected correct)
          (message "Correct! %s" explanation)
        (message "Incorrect. The correct answer is: %s. %s" correct-answer explanation)))))

(defun aws-ai-practice-show-explanation ()
  "Show the explanation for the current question."
  (interactive)
  (save-excursion
    (org-back-to-heading t)
    (let ((explanation (org-entry-get nil "EXPLANATION"))
          (last-answered (org-entry-get nil "LAST_ANSWERED")))
      (if last-answered
          (message "Explanation: %s\nLast answered: %s" explanation last-answered)
        (message "Explanation: %s\nNot answered yet." explanation)))))

(defun aws-ai-practice-show-stats ()
  "Show statistics for the current practice file."
  (interactive)
  (let ((total 0)
        (answered 0))
    (org-map-entries
     (lambda ()
       (setq total (1+ total))
       (when (org-entry-get nil "LAST_ANSWERED")
         (setq answered (1+ answered))))
     t 'file)
    (message "Progress: %d/%d questions answered (%.2f%%)"
             answered total (* 100.0 (/ answered (float total))))))

(defun aws-ai-practice-reset-all-answers ()
  "Reset all answers in the current practice file."
  (interactive)
  (when (yes-or-no-p "Are you sure you want to reset all answers? ")
    (org-map-entries
     (lambda ()
       (let ((options (org-entry-get-multivalued-property nil "ITEM")))
         (when options
           (setq options (mapcar (lambda (opt) (replace-regexp-in-string "\\[X\\]" "[ ]" opt)) options))
           (org-entry-put-multivalued-property nil "ITEM" options))
         (org-entry-delete nil "LAST_ANSWERED")))
     t 'file)
    (message "All answers have been reset.")))

(define-minor-mode aws-ai-practice-mode
  "Minor mode for AWS AI Fundamentals practice questions."
  :lighter " AWS-AI"
  :keymap (let ((map (make-sparse-keymap)))
            (define-key map (kbd "C-c C-c") 'aws-ai-practice-check-answer)
            (define-key map (kbd "C-c C-e") 'aws-ai-practice-show-explanation)
            (define-key map (kbd "C-c C-s") 'aws-ai-practice-show-stats)
            (define-key map (kbd "C-c C-t") 'aws-ai-practice-toggle-property-visibility)
            (define-key map (kbd "C-c C-a") 'aws-ai-practice-set-answer)
            (define-key map (kbd "C-c C-r") 'aws-ai-practice-reset-all-answers)
            map))

(defun aws-ai-practice-mode-init ()
  "Initialize AWS AI practice mode."
  (aws-ai-practice-update-property-visibility))

(add-hook 'org-mode-hook
          (lambda ()
            (when (and buffer-file-name
                       (string-match "aif-c01-practice-" (buffer-file-name)))
              (aws-ai-practice-mode 1)
              (aws-ai-practice-mode-init))))

(provide 'aws-ai-practice)

;;; aws-ai-practice.el ends here
