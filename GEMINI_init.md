# Gemini Project Initialization & Collaboration Template

This document outlines the standard operating procedures, development pipeline, and best practices for initiating and executing new projects with Gemini. Following this template will ensure a smooth, efficient, and high-quality collaboration from the outset.

## 1. Project Kick-off & Scoping

Before we begin, please provide the following information:

*   **Project Goal:** What is the primary objective of this project? What problem are we solving?
*   **Core Features:** List the essential features for the initial version (MVP).
*   **Technology Stack:** Do you have a preferred technology stack (e.g., Python/Django, React/Node, etc.)? If not, I will propose one based on the project requirements.
*   **Existing Codebase:** Is there any existing code? If so, please provide access or a summary.
*   **External Services/APIs:** Will the project need to integrate with any third-party services or APIs?

Based on your answers, I will propose a high-level plan, including the application architecture and the initial setup steps.

## 2. Development Pipeline: Test-Driven Development (TDD)

We will adhere to a strict Test-Driven Development (TDD) workflow to ensure code quality, maintainability, and robustness.

**The TDD Cycle (Red-Green-Refactor):**

1.  **Red (Write a Failing Test):** Before writing any implementation code, I will first write a test that defines the desired functionality. This test will fail initially, confirming that the feature is not yet implemented.
2.  **Green (Write Minimum Code to Pass):** I will then write the simplest, most direct code required to make the failing test pass. The goal is to get to a "green" state quickly.
3.  **Refactor (Improve Code Quality):** With the safety of a passing test, I will refactor the code to improve its structure, remove duplication, and ensure it adheres to best practices, all while keeping the tests green.

This iterative cycle will be applied to all new features, bug fixes, and refactoring tasks.

## 3. Best Practices

*   **Code Style & Formatting:** We will use automated tools to maintain a consistent code style.
    *   **Python:** `black` for formatting and `ruff` for linting.
    *   *(Other languages will have equivalent standard tools, e.g., `prettier` for JavaScript/TypeScript).*
*   **Git Workflow:**
    *   All changes will be committed to a Git repository.
    *   I will write clear, descriptive commit messages explaining the "why" behind the changes.
    *   I will always run tests and linters before proposing a commit.
*   **Dependencies:** Project dependencies will be explicitly managed in a requirements file (e.g., `requirements.txt` for Python, `package.json` for Node.js).
*   **Secrets Management:** No API keys, passwords, or other sensitive data will ever be hardcoded into the source code. We will use environment variables or a dedicated secrets management solution.

## 4. Essential Commands

For a typical Python/Django project, these are the commands we will use frequently. I will identify and use the equivalent commands for other technology stacks.

*   **Install/Synchronize Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
*   **Apply Database Migrations**:
    ```bash
    python manage.py migrate
    ```
*   **Run Tests**:
    ```bash
    python manage.py test
    ```
*   **Code Formatting**:
    ```bash
    black .
    ```
*   **Linting**:
    ```bash
    ruff check .
    ```

## 5. Our Collaboration

*   **Clarity:** I will rephrase your requests to ensure I have understood them correctly, especially for complex tasks.
*   **Proactiveness:** I will try to anticipate next steps and make logical follow-up actions, but I will always ask for confirmation before proceeding with significant changes.
*   **Planning:** For any non-trivial task, I will first analyze the codebase and present a clear plan of action before making changes.
*   **Feedback:** Your feedback is crucial. Please let me know if my approach or suggestions can be improved.

By following this template, we can build amazing things together efficiently and reliably.
