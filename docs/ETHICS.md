# Ethics, Privacy and Limitations

Implements Proposal §3.13 (Ethical Considerations).

## Decision-support, not diagnosis
Every result page, the site banner and the footer state: **"Decision-support
only, not a medical diagnosis."** High-risk results direct the person to a
professional and show an emergency number. Clinicians are reminded to use the
estimate alongside clinical judgement.

## Informed consent
Each assessment requires explicit consent (checkbox). The database refuses to
store an assessment without it (`consent_given` must be 1).

## Confidentiality and access control
- Passwords are stored as salted hashes (werkzeug scrypt), never in plain text.
- **Least privilege:** service members see only their own results; clinicians see
  assessments; administrators manage the system but **cannot** open assessment answers.
- Roles are checked on the server for every page; attempts to reach another
  role's page are refused (403) and logged.
- Only service members can self-register; staff accounts are created by administrators.
- **Audit trail:** sign-ins, failed sign-ins, assessments submitted, every
  clinician view of a record, notes and admin changes are logged with time and IP.
- Sessions expire after 30 minutes; 5 failed sign-ins lock an account for 15 minutes;
  CSRF tokens and security headers protect against common web attacks.
- In production the site is served only over HTTPS with secure cookies.
- The summary report shows aggregate figures only (no names), for sharing with management.

## Data used in this project
Only **synthetic** (computer-generated) data and **fictional** demo accounts
(`@demo.local`) are used. No real personal or health data was collected or used.
Usability testing participants would be informed of the study's purpose and
give consent before taking part.

## Algorithmic bias and fairness
- Logistic Regression is transparent: every input's weight is published on the
  "About the model" page, and each result shows the factors that drove it.
- Gender is an input. On synthetic data this cannot introduce real-world bias,
  but a model trained on real data must be checked for different error rates
  across gender and other groups before use.

## Limitations
1. **Synthetic training data.** Performance figures demonstrate the method, not
   real-world accuracy. Retraining and validation on approved real data are
   required before operational use.
2. **Self-reported answers** may be inaccurate (under-reporting because of stigma).
3. **Precision of 0.36** means about two in three high-risk flags are false alarms.
   This is acceptable for screening followed by clinical review, not for decisions
   about a person's career or duties.
4. SQLite suits this scale; a large deployment would move to a client-server
   database (e.g. MySQL/PostgreSQL) with encryption at rest.
5. Operational deployment in Kenya would require review under the **Data
   Protection Act, 2019** and approval by the organisation's data protection officer.
