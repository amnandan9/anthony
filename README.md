# St. Anthony Coaching Center Portal

The **St. Anthony Coaching Center Portal** is a premium web application designed to manage student registration, attendance tracking, and fee collection workflows for educational coaching centers. It offers administrators and teachers an automated, secure, and visually premium interface for handling daily coaching center activities.

---

## Key Features

### 1. Student & Profile Management
* **Flexible Student Profiles**: Tracks student details including Name, Batch, Class/Std (e.g., "1st", "10th Std"), School/College, and Contact Numbers. Email address fields are optional to facilitate easy registration.
* **Batch Scheduling**: Organizes students into distinct batches (e.g., Morning Science, Evening Maths, Weekend Programming) with dynamic timing and schedule views.

### 2. High-Performance Scanner Terminal (Dual-Mode)
* **Direct QR Code Scanning**: Scan printed student QR cards using standard device webcams for high-throughput class check-ins and billing queries. Features dynamic detection boundaries and optimized frame rates.
* **Direct Face Recognition**: Compares webcam frames against registered database templates using a custom spatial pixel-shift matching algorithm designed to handle scaling, offsets, and varied webcam resolutions.
* **Self-Refining Facial Verification**: Automatically updates the reference image in the student's profile on a successful match to adapt to recent changes in appearance.

### 3. Billing & Fee Collection Scanner
* **Billing Lookup**: Automatically retrieves the student's current billing details, monthly dues, and recommended next due date upon QR or Face detection.
* **Quick Payment Recording**: Allows teachers and administrators to instantly record payments with remarks (e.g., Paid in Cash) directly from the scanning terminal.
* **Smart UI Lifecycle**: Auto-closes billing modals after 20 seconds of inactivity to clear the screen, but cancels the auto-close timer as soon as a teacher focuses on any input field.

### 4. Public Student Info Check
* **Kiosk Info Scan**: A secure, unauthenticated QR scanner embedded on the public login page that allows students to scan their card to view their Batch, School, Attendance Streak (this month), and Next Due Date.
* **Privacy Controls**: Sensitive information, such as the monthly fee amount, is strictly hidden from the public info view.

### 5. Premium Dashboard & Security Enforcements
* **Role-Based Views**: Tailored dashboards for Super Admins (managing teachers, overall statistics), Teachers (scheduling classes, viewing profiles), and Students (viewing personal history).
* **Automatic Reloading**: Scanner terminals automatically refresh the page upon closing success modals. It persists the current scanner mode (QR or Face) across reloads to prevent hardware locks and keep the camera stream fresh.
* **Enforced HTTPS Security**: Automated routing-level redirects, secure production cookies, and Strict Transport Security (HSTS) settings to ensure absolute protection against credential and data leaks.