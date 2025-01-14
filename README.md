# EMS CI/CD Pipeline Documentation

## Overview

This repository contains the Continuous Integration and Continuous Deployment (CI/CD) pipeline for the **Election Managment System** project. The pipeline is set up using **Jenkins**, and it automates the process of building and testing the application. This document outlines the steps to run the pipeline and troubleshooting tips for common issues.

---

## Pipeline Overview

The pipeline is designed to perform the following stages:

1. **Checkout**:
   - The latest code is pulled from the repository using Git.
2. **Build**:
   - Dependencies from the `requirements.txt` file are installed using `pip`.
3. **Test**:
   - The project is tested using **pytest**. Any failing tests will cause the pipeline to fail.

These stages are defined in the `Jenkinsfile` located at the root of the repository.

---

## How to Run the Pipeline

### Prerequisites:

1. **Jenkins** should be installed and configured.
2. You need **GitHub** credentials set up in Jenkins for the repository.
3. Ensure the following plugins are installed in Jenkins:
   - **Git Plugin**
   - **Pipeline Plugin**
   - **SSH Pipeline Steps**

### Steps to Run the Pipeline:

1. **Clone the repository** to your Jenkins server (or configure your Jenkins job to pull from GitHub directly).
2. **Create a new Jenkins pipeline job**:

   - Go to `Jenkins Dashboard > New Item > Pipeline`.
   - Enter a name for the job (e.g., `EMS-CI-CD`).
   - Under `Pipeline`, choose `Pipeline script from SCM`.
   - Select the **Git** option and enter the repository URL.
   - Set the branch to `main` (or your relevant branch).
   - Specify the `Jenkinsfile` path if it is not in the root directory.

3. **Trigger the pipeline**:
   - The pipeline will run automatically after a commit is made to the repository (if webhooks are configured).
   - Alternatively, you can manually trigger the pipeline by clicking on `Build Now` from the Jenkins dashboard.

---

## Additional Information

For more detailed information on setting up and managing Jenkins pipelines, refer to the [Jenkins documentation](https://www.jenkins.io/doc/).
