;; Initialize package sources
(require 'package)
(setq package-archives '(("melpa" . "https://melpa.org/packages/")
                         ("org" . "https://orgmode.org/elpa/")
                         ("elpa" . "https://elpa.gnu.org/packages/")))

(package-initialize)
(unless package-archive-contents
  (package-refresh-contents))

;; Initialize use-package
(unless (package-installed-p 'use-package)
  (package-install 'use-package))
(require 'use-package)
(setq use-package-always-ensure t)

;; Clojure mode
(use-package clojure-mode
  :mode (("\\.clj\\'" . clojure-mode)
         ("\\.edn\\'" . clojure-mode)))

;; CIDER (Clojure Interactive Development Environment that Rocks)
(use-package cider
  :hook (clojure-mode . cider-mode))

;; Company mode for completion
(use-package company
  :hook (after-init . global-company-mode))

;; ParEdit for structural editing
(use-package paredit
  :hook ((clojure-mode . enable-paredit-mode)
         (cider-repl-mode . enable-paredit-mode)))

;; Rainbow delimiters
(use-package rainbow-delimiters
  :hook (prog-mode . rainbow-delimiters-mode))

;; Magit for Git integration
(use-package magit)

;; Org mode
(use-package org
  :config
  (setq org-startup-indented t))

(org-babel-do-load-languages
 'org-babel-load-languages
 '((shell . t)
   (python . t)
   (clojure . t)
   (mermaid . t)))

;; Mermaid setup (make sure mermaid-cli is installed)
(use-package ob-mermaid
  :ensure t
  :config
  (setq ob-mermaid-cli-path "/usr/local/bin/mmdc"))

;; Optional: Set up CIDER for Clojure integration
(use-package cider
  :ensure t
  :config
  (setq org-babel-clojure-backend 'cider))

;; Optional: Don't ask for confirmation when executing code blocks
(setq org-confirm-babel-evaluate nil)


;; Theme
(use-package doom-themes
  :config
  (load-theme 'doom-one t))

;; Projectile for project management
(use-package projectile
  :config
  (projectile-mode +1)
  :bind-keymap
  ("C-c p" . projectile-command-map))

;; Refactoring
(use-package clj-refactor
  :hook (clojure-mode . clj-refactor-mode)
  :config
  (cljr-add-keybindings-with-prefix "C-c C-m"))

;; Customizations
(setq-default
 inhibit-startup-screen t
 initial-scratch-message nil
 sentence-end-double-space nil
 ring-bell-function 'ignore
 use-dialog-box nil
 use-file-dialog nil)

(menu-bar-mode -1)
(tool-bar-mode -1)
(scroll-bar-mode -1)
(global-display-line-numbers-mode 1)

(provide 'init)
