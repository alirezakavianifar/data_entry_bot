
# Google Sheets Integration & Setup Guide

This guide provides step-by-step instructions for setting up your own Google Sheet as the live data source for the **Data Entry Bot**.

---

## 📋 Overview of How It Works

1. **Input Data Tab (`Client Details`):** The bot reads client contact and identity information from this sheet.
2. **Output Data Tab (`Succesful Signuos`):** When account registrations succeed, the bot automatically records the credentials and timestamps here.
3. **Authentication:** The desktop application communicates securely with your Google Sheet using a **Google Service Account key (`credentials.json`)**.

---

## 📑 Step 1: Prepare Your Google Spreadsheet

You can either create a new Google Sheet or copy an existing template.

### 1. Tab Names

Your Google Spreadsheet must contain **two tabs** (worksheets) at the bottom:

1. **`Client Details`** (Input)
2. **`Succesful Signuos`** (Output — or named `Successful Signups`)

---

### 2. Tab 1 Structure: `Client Details`

* **Row 1 & 2:** Can contain notes or titles (the bot automatically searches the first 10 rows for the table headers).
* **Row 3:** Column headers (must match these column names):

| Column      | Header Name        | Description / Format                                  | Example                            |
| :---------- | :----------------- | :---------------------------------------------------- | :--------------------------------- |
| **A** | `Client`         | Full Name                                             | `Courtney Weaver`                |
| **B** | `First name`     | First Name                                            | `Courtney`                       |
| **C** | `Last name`      | Last Name                                             | `Weaver`                         |
| **D** | `DOB`            | Date of Birth (`DD/MM/YYYY` or Date format)         | `17/05/2001`                     |
| **E** | `Email`          | Client's Email                                        | `courtney.weaver.5580@gmail.com` |
| **F** | `Phone`          | UK Mobile Phone Number                                | `07466317822`                    |
| **G** | `Address line 1` | House number and street name                          | `59 Keats Avenue`                |
| **H** | `Town / City`    | Town or City                                          | `Romford, Essex`                 |
| **I** | `Postcode`       | UK Postal Code                                        | `RM3 7AX`                        |
| **J** | `Country`        | Country (defaults to`United Kingdom` if left blank) | `United Kingdom`                 |
| **K** | `Card used`      | Payment Card reference (optional)                     | `Melissa Kapp - 2477`            |
| **L** | `Allocated VA`   | Assigned Virtual Assistant (optional)                 | `Kimbo`                          |
| **M** | `Notes`          | Additional client notes (optional)                    | *(optional)*                     |

* **Row 4 onwards:** Your client records.

---

### 3. Tab 2 Structure: `Succesful Signuos`

* **Row 1:** Header row:
  ```text
  Name | Account | Email | Username | Password | Timestamp | Notes
  ```
* **Row 2 onwards:** Leave blank! The bot will automatically populate this tab when accounts are created.
  *(Note: If this tab is not present, the bot will automatically create it upon the first successful registration).*

---

## 🔑 Step 2: Create a Google Cloud Service Account (`credentials.json`)

To allow the desktop application to read and write to your Google Sheet, Google requires an API key called a Service Account. This takes about **3 minutes** to set up:

### 1. Open Google Cloud Console

1. Go to **[https://console.cloud.google.com/](https://console.cloud.google.com/)** and sign in with your Google account.
2. At the top of the page, click the project dropdown and click **"New Project"**.
3. Name your project (e.g. `Data Entry Automation`) and click **Create**.

---

### 2. Enable Required Google APIs

1. In the top search bar, type **`Google Sheets API`** and press Enter.
   * Click on **Google Sheets API** in the results, then click the blue **`Enable`** button.
2. In the top search bar, type **`Google Drive API`** and press Enter.
   * Click on **Google Drive API** in the results, then click the blue **`Enable`** button.

---

### 3. Create the Service Account

1. Open the left navigation menu (`☰`) and navigate to **APIs & Services** ➔ **Credentials**.
2. Click **`+ CREATE CREDENTIALS`** at the top and select **`Service account`**.
3. Set the **Service account name** to: `data-entry-bot`.
4. Click **`CREATE AND CONTINUE`**, and then click **`DONE`** (roles can be left default).

---

### 4. Download `credentials.json`

1. On the **Credentials** page, scroll down to **Service Accounts** and click on the email address you just created (e.g. `data-entry-bot@your-project-id.iam.gserviceaccount.com`).
2. Click on the **`KEYS`** tab at the top.
3. Click **`Add Key`** ➔ **`Create new key`**.
4. Choose **`JSON`** and click **`CREATE`**.
5. A `.json` file will automatically download to your computer.

---

## 📂 Step 3: Place `credentials.json` in the Application Directory

1. Locate the downloaded JSON file on your computer.
2. **Rename** the file to exactly:
   ```text
   credentials.json
   ```
3. Move or copy **`credentials.json`** directly into the folder where the application is installed:
   * **If running from source:** Place it in the root project folder (next to `gui_app.py` and `app.py`).
   * **If running Portable Standalone:** Place it in the same folder as `DataEntryBot.exe`.

---

## 🔗 Step 4: Share Your Google Sheet with the Service Account

1. Open your `credentials.json` file using Notepad or any text editor.
2. Look for the line starting with `"client_email"`. It will look like:
   ```json
   "client_email": "data-entry-bot@your-project-id.iam.gserviceaccount.com"
   ```
3. Copy that email address.
4. Open your **Google Spreadsheet** in your web browser.
5. Click the **Share** button in the top-right corner.
6. Paste the copied email address into the **"Add people and groups"** box.
7. Set the permission level to **`Editor`**.
8. Uncheck "Notify people" (optional) and click **Share / Send**.

---

## 🚀 Step 5: Run the Desktop Application

### Using the Desktop GUI:

1. Double-click **`run_desktop_app.bat`** (or **`DataEntryBot.exe`**).
2. In the left sidebar:
   * Change **Data Source** from `Excel (.xlsx)` to **`Google Sheets`**.
   * In the **Google Sheet URL** field, paste your spreadsheet's shareable link:
     ```text
     https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit?usp=sharing
     ```
3. Select your target bookmaker websites.
4. (Optional) Click **`🧪 Dry Run (Check Data)`** to test reading clients without opening registration pages.
5. Click **`🚀 Start Automation`** to begin live registration.

---

## 🛠️ Troubleshooting & Frequently Asked Questions

### 1. Error: `Google service account credentials not found at: credentials.json`

* **Fix:** Make sure `credentials.json` is located in the exact same directory as `DataEntryBot.exe` or `gui_app.py` and is named exactly `credentials.json` (not `credentials.json.json`).

### 2. Error: `gspread.exceptions.SpreadsheetNotFound` or `API Error 403 / 404`

* **Cause:** The Google Sheet has not been shared with the service account.
* **Fix:** Open `credentials.json`, copy the `"client_email"` address, and ensure it is added as an **Editor** in the Google Sheet's **Share** settings.

### 3. Error: `API has not been used in project ... before or it is disabled`

* **Fix:** Make sure both **Google Sheets API** and **Google Drive API** are enabled in your Google Cloud Console project.

### 4. No clients are loaded or 0 clients found

* **Fix:** Check your input tab name. It must be named **`Client Details`** (case-insensitive).
* Ensure Row 3 contains the column headers (`Client`, `First name`, `Last name`, `DOB`, `Email`, `Phone`, `Address line 1`, `Town / City`, `Postcode`).

### 5. Dates of birth are rejected or skipped

* **Fix:** Ensure DOB values are formatted as either standard Date cells or `DD/MM/YYYY` text strings (e.g. `17/05/2001`).
