// AccountHub Legal Pages Worker
// Serves Terms of Service and Privacy Policy

const TERMS_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Terms of Service — AccountHub</title>
  <meta name="description" content="AccountHub Terms of Service. Read about the terms and conditions governing your use of the AccountHub application.">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      color: #1a1a2e;
      background: #f8f9fb;
      line-height: 1.7;
      -webkit-font-smoothing: antialiased;
    }
    header {
      background: #fff;
      border-bottom: 1px solid #e5e7eb;
      padding: 1rem 2rem;
      position: sticky;
      top: 0;
      z-index: 10;
    }
    header .inner {
      max-width: 800px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    header .logo {
      font-weight: 700;
      font-size: 1.15rem;
      color: #1a1a2e;
      text-decoration: none;
    }
    header nav a {
      color: #555;
      text-decoration: none;
      font-size: 0.9rem;
      margin-left: 1.5rem;
      transition: color 0.2s;
    }
    header nav a:hover, header nav a.active { color: #2563eb; }
    main {
      max-width: 800px;
      margin: 0 auto;
      padding: 3rem 2rem 5rem;
    }
    .doc-header {
      text-align: center;
      margin-bottom: 2.5rem;
      padding-bottom: 2rem;
      border-bottom: 2px solid #e5e7eb;
    }
    .doc-header h1 {
      font-size: 2rem;
      font-weight: 700;
      margin-bottom: 0.25rem;
      color: #1a1a2e;
    }
    .doc-header .subtitle {
      font-size: 1.35rem;
      font-weight: 600;
      color: #374151;
      margin-bottom: 0.75rem;
    }
    .doc-header .effective {
      font-size: 0.9rem;
      color: #6b7280;
    }
    h2 {
      font-size: 1.25rem;
      font-weight: 700;
      color: #1a1a2e;
      margin-top: 2.25rem;
      margin-bottom: 0.75rem;
    }
    p { margin-bottom: 1rem; color: #374151; }
    ul {
      margin: 0.5rem 0 1rem 1.5rem;
      color: #374151;
    }
    ul li {
      margin-bottom: 0.4rem;
      padding-left: 0.25rem;
    }
    .contact-block {
      background: #f1f5f9;
      border-radius: 8px;
      padding: 1.25rem 1.5rem;
      margin-top: 1rem;
    }
    .contact-block p { margin-bottom: 0.35rem; }
    footer {
      text-align: center;
      padding: 2rem;
      color: #9ca3af;
      font-size: 0.85rem;
      border-top: 1px solid #e5e7eb;
    }
    @media (max-width: 640px) {
      main { padding: 2rem 1.25rem 3rem; }
      .doc-header h1 { font-size: 1.5rem; }
    }
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <a href="https://AccountHub.dlopro.ca" class="logo">AccountHub</a>
      <nav>
        <a href="/terms" class="active">Terms</a>
        <a href="/privacy">Privacy</a>
      </nav>
    </div>
  </header>

  <main>
    <div class="doc-header">
      <h1>AccountHub</h1>
      <div class="subtitle">Terms of Service</div>
      <div class="effective">Effective Date: April 13, 2026</div>
    </div>

    <h2>1. Acceptance of Terms</h2>
    <p>By downloading, installing, accessing, or using AccountHub (the &ldquo;Application&rdquo;), you agree to be bound by these Terms of Service (the &ldquo;Terms&rdquo;). If you do not agree to these Terms, do not use the Application. These Terms constitute a legally binding agreement between you (&ldquo;User&rdquo; or &ldquo;you&rdquo;) and Derek Kemle (&ldquo;Operator,&rdquo; &ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;).</p>
    <p>We reserve the right to update or modify these Terms at any time. Your continued use of the Application after any changes constitutes acceptance of the revised Terms. We will make reasonable efforts to notify you of material changes.</p>

    <h2>2. Description of Service</h2>
    <p>AccountHub is a desktop application that allows users to input email information to discover and manage accounts associated with that email address from a centralized interface (the &ldquo;Service&rdquo;). The Service may include features for account discovery, organization, and management.</p>

    <h2>3. Eligibility</h2>
    <p>You must be at least 18 years of age (or the age of majority in your jurisdiction) to use the Application. By using the Application, you represent and warrant that you meet this age requirement and have the legal capacity to enter into these Terms.</p>

    <h2>4. User Accounts and Registration</h2>
    <p>To use certain features of the Application, you may be required to provide information, including but not limited to a valid email address. You agree to:</p>
    <ul>
      <li>Provide accurate, current, and complete information</li>
      <li>Maintain the security and confidentiality of any credentials associated with the Application</li>
      <li>Promptly notify us of any unauthorized use of the Application on your device</li>
      <li>Accept responsibility for all activities that occur under your use of the Application</li>
    </ul>

    <h2>5. Acceptable Use</h2>
    <p>You agree not to use the Application to:</p>
    <ul>
      <li>Violate any applicable local, state, provincial, national, or international law or regulation</li>
      <li>Access accounts or information belonging to another person without their authorization</li>
      <li>Attempt to gain unauthorized access to any third-party service, system, or network</li>
      <li>Interfere with or disrupt the integrity or performance of the Application</li>
      <li>Reverse engineer, decompile, disassemble, or otherwise attempt to derive the source code of the Application</li>
      <li>Use the Application for any fraudulent, abusive, or otherwise harmful purpose</li>
      <li>Transmit any viruses, malware, or other malicious code through the Application</li>
      <li>Scrape, harvest, or collect information from third-party services in violation of their terms</li>
    </ul>

    <h2>6. Intellectual Property</h2>
    <p>All rights, title, and interest in and to the Application, including all intellectual property rights, are owned by Derek Kemle. These Terms grant you a limited, non-exclusive, non-transferable, revocable license to use the Application for personal, non-commercial purposes, unless a separate commercial license is obtained.</p>
    <p>You may not copy, modify, distribute, sell, lease, or create derivative works based on the Application or any part thereof without prior written consent from the Operator.</p>

    <h2>7. Third-Party Services</h2>
    <p>The Application may interact with third-party websites, services, or APIs to discover and manage your accounts. We are not responsible for the availability, accuracy, or content of any third-party services. Your use of third-party services is subject to those services&rsquo; own terms and privacy policies.</p>
    <p>We do not endorse, warrant, or assume responsibility for any third-party service, product, or content. Any transactions or interactions between you and a third party are solely between you and that third party.</p>

    <h2>8. Fees and Payment</h2>
    <p>The Application may be offered free of charge or may include paid features, subscriptions, or one-time purchases (&ldquo;Paid Services&rdquo;). If Paid Services are introduced, applicable pricing and payment terms will be disclosed to you before any charges are incurred. By purchasing Paid Services, you agree to pay the applicable fees.</p>
    <p>We reserve the right to modify pricing for Paid Services at any time, with reasonable advance notice. Changes will not affect the current billing period for existing subscribers.</p>

    <h2>9. Disclaimer of Warranties</h2>
    <p>THE APPLICATION IS PROVIDED ON AN &ldquo;AS IS&rdquo; AND &ldquo;AS AVAILABLE&rdquo; BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT.</p>
    <p>We do not warrant that the Application will be uninterrupted, error-free, secure, or free of viruses or other harmful components. We do not guarantee the accuracy or completeness of any account information discovered through the Application.</p>

    <h2>10. Limitation of Liability</h2>
    <p>TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, IN NO EVENT SHALL DEREK KEMLE, OR ANY AFFILIATES, AGENTS, OR LICENSORS, BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING BUT NOT LIMITED TO LOSS OF PROFITS, DATA, USE, OR GOODWILL, ARISING OUT OF OR IN CONNECTION WITH YOUR USE OF OR INABILITY TO USE THE APPLICATION.</p>
    <p>OUR TOTAL AGGREGATE LIABILITY ARISING OUT OF OR RELATING TO THESE TERMS OR THE APPLICATION SHALL NOT EXCEED THE GREATER OF (A) THE AMOUNT YOU HAVE PAID TO US IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM, OR (B) ONE HUNDRED U.S. DOLLARS (\$100.00 USD).</p>

    <h2>11. Indemnification</h2>
    <p>You agree to indemnify, defend, and hold harmless Derek Kemle from and against any and all claims, damages, obligations, losses, liabilities, costs, and expenses (including reasonable attorney&rsquo;s fees) arising from: (a) your use of the Application; (b) your violation of these Terms; (c) your violation of any third-party right, including any intellectual property or privacy right; or (d) any claim that your use of the Application caused damage to a third party.</p>

    <h2>12. Termination</h2>
    <p>We may suspend or terminate your access to the Application at any time, with or without cause, and with or without notice. Upon termination, your right to use the Application will immediately cease.</p>
    <p>You may terminate your use of the Application at any time by uninstalling it from your device. Sections that by their nature should survive termination (including but not limited to Sections 6, 9, 10, 11, and 14) shall survive.</p>

    <h2>13. Privacy</h2>
    <p>Your use of the Application is also governed by our <a href="/privacy">Privacy Policy</a>, which describes how we collect, use, and protect your personal information. By using the Application, you consent to the practices described in the Privacy Policy. The Privacy Policy is incorporated into these Terms by reference.</p>

    <h2>14. Governing Law and Dispute Resolution</h2>
    <p>These Terms shall be governed by and construed in accordance with the laws of the United States and the state in which the Operator resides, without regard to conflict of law principles.</p>
    <p>Any dispute arising out of or relating to these Terms or the Application shall first be attempted to be resolved through good-faith negotiation. If the dispute cannot be resolved through negotiation within thirty (30) days, either party may pursue resolution through binding arbitration or in the courts of competent jurisdiction in the Operator&rsquo;s state of residence.</p>

    <h2>15. Severability</h2>
    <p>If any provision of these Terms is held to be invalid, illegal, or unenforceable, the remaining provisions shall continue in full force and effect. The invalid provision shall be modified to the minimum extent necessary to make it valid and enforceable while preserving the original intent.</p>

    <h2>16. Entire Agreement</h2>
    <p>These Terms, together with the Privacy Policy and any additional terms for Paid Services, constitute the entire agreement between you and the Operator regarding the use of the Application and supersede all prior agreements and understandings, whether written or oral.</p>

    <h2>17. Contact Information</h2>
    <p>If you have any questions or concerns about these Terms, please contact us at:</p>
    <div class="contact-block">
      <p><strong>Name:</strong> Derek Kemle</p>
      <p><strong>Email:</strong> dereklawrencekemle@icloud.com</p>
    </div>
  </main>

  <footer>
    &copy; 2026 Derek Kemle. All rights reserved.
  </footer>
</body>
</html>
`;

const PRIVACY_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Privacy Policy — AccountHub</title>
  <meta name="description" content="AccountHub Privacy Policy. Learn how we collect, use, and protect your personal information.">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      color: #1a1a2e;
      background: #f8f9fb;
      line-height: 1.7;
      -webkit-font-smoothing: antialiased;
    }
    header {
      background: #fff;
      border-bottom: 1px solid #e5e7eb;
      padding: 1rem 2rem;
      position: sticky;
      top: 0;
      z-index: 10;
    }
    header .inner {
      max-width: 800px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    header .logo {
      font-weight: 700;
      font-size: 1.15rem;
      color: #1a1a2e;
      text-decoration: none;
    }
    header nav a {
      color: #555;
      text-decoration: none;
      font-size: 0.9rem;
      margin-left: 1.5rem;
      transition: color 0.2s;
    }
    header nav a:hover, header nav a.active { color: #2563eb; }
    main {
      max-width: 800px;
      margin: 0 auto;
      padding: 3rem 2rem 5rem;
    }
    .doc-header {
      text-align: center;
      margin-bottom: 2.5rem;
      padding-bottom: 2rem;
      border-bottom: 2px solid #e5e7eb;
    }
    .doc-header h1 {
      font-size: 2rem;
      font-weight: 700;
      margin-bottom: 0.25rem;
      color: #1a1a2e;
    }
    .doc-header .subtitle {
      font-size: 1.35rem;
      font-weight: 600;
      color: #374151;
      margin-bottom: 0.75rem;
    }
    .doc-header .effective {
      font-size: 0.9rem;
      color: #6b7280;
    }
    h2 {
      font-size: 1.25rem;
      font-weight: 700;
      color: #1a1a2e;
      margin-top: 2.25rem;
      margin-bottom: 0.75rem;
    }
    h3 {
      font-size: 1.05rem;
      font-weight: 600;
      color: #374151;
      margin-top: 1.5rem;
      margin-bottom: 0.5rem;
    }
    p { margin-bottom: 1rem; color: #374151; }
    ul {
      margin: 0.5rem 0 1rem 1.5rem;
      color: #374151;
    }
    ul li {
      margin-bottom: 0.4rem;
      padding-left: 0.25rem;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 1rem 0 1.5rem;
      font-size: 0.95rem;
    }
    th, td {
      text-align: left;
      padding: 0.75rem 1rem;
      border: 1px solid #e5e7eb;
      color: #374151;
    }
    th {
      background: #e8f0fe;
      font-weight: 600;
      color: #1a1a2e;
    }
    tr:nth-child(even) td { background: #fafbfc; }
    .contact-block {
      background: #f1f5f9;
      border-radius: 8px;
      padding: 1.25rem 1.5rem;
      margin-top: 1rem;
    }
    .contact-block p { margin-bottom: 0.35rem; }
    footer {
      text-align: center;
      padding: 2rem;
      color: #9ca3af;
      font-size: 0.85rem;
      border-top: 1px solid #e5e7eb;
    }
    @media (max-width: 640px) {
      main { padding: 2rem 1.25rem 3rem; }
      .doc-header h1 { font-size: 1.5rem; }
      table { font-size: 0.85rem; }
      th, td { padding: 0.5rem 0.65rem; }
    }
  </style>
</head>
<body>
  <header>
    <div class="inner">
      <a href="https://AccountHub.dlopro.ca" class="logo">AccountHub</a>
      <nav>
        <a href="/terms">Terms</a>
        <a href="/privacy" class="active">Privacy</a>
      </nav>
    </div>
  </header>

  <main>
    <div class="doc-header">
      <h1>AccountHub</h1>
      <div class="subtitle">Privacy Policy</div>
      <div class="effective">Effective Date: April 13, 2026</div>
    </div>

    <h2>1. Introduction</h2>
    <p>Derek Kemle (&ldquo;Operator,&rdquo; &ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;) operates AccountHub (the &ldquo;Application&rdquo;). This Privacy Policy explains how we collect, use, disclose, and safeguard your personal information when you use the Application. By using the Application, you consent to the data practices described in this policy.</p>
    <p>We are committed to protecting your privacy. Please read this Privacy Policy carefully. If you do not agree with the terms of this Privacy Policy, please do not use the Application.</p>

    <h2>2. Information We Collect</h2>

    <h3>2.1 Information You Provide Directly</h3>
    <p>When you use the Application, you may provide us with the following types of information:</p>
    <ul>
      <li><strong>Email Address(es):</strong> You input one or more email addresses so the Application can discover associated accounts.</li>
      <li><strong>Account Credentials:</strong> If applicable, you may provide login credentials to enable the Application to access and manage your accounts on your behalf. These credentials are handled with the highest level of security.</li>
      <li><strong>Profile Information:</strong> Any preferences, settings, or organizational labels you configure within the Application.</li>
    </ul>

    <h3>2.2 Information Collected Automatically</h3>
    <p>When you use the Application, we may automatically collect:</p>
    <ul>
      <li><strong>Device Information:</strong> Operating system, device type, and hardware identifiers.</li>
      <li><strong>Usage Data:</strong> Features used, frequency of use, crash reports, and performance data.</li>
      <li><strong>Log Data:</strong> Timestamps, error logs, and diagnostic information to help us improve the Application.</li>
    </ul>

    <h3>2.3 Information from Third-Party Services</h3>
    <p>When the Application discovers and interacts with accounts associated with your email, it may receive information from third-party services, including account names, account types, registration dates, and associated profile data. We only access information necessary to provide the Service.</p>

    <h2>3. How We Use Your Information</h2>
    <p>We use the information we collect for the following purposes:</p>
    <table>
      <thead>
        <tr>
          <th>Purpose</th>
          <th>Description</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Service Delivery</td>
          <td>To discover, display, and manage accounts associated with your email address</td>
        </tr>
        <tr>
          <td>Improvement</td>
          <td>To analyze usage patterns and improve the Application&rsquo;s features and performance</td>
        </tr>
        <tr>
          <td>Security</td>
          <td>To detect, prevent, and address technical issues, fraud, or security threats</td>
        </tr>
        <tr>
          <td>Communication</td>
          <td>To send you service-related notices, updates, and support responses</td>
        </tr>
        <tr>
          <td>Legal Compliance</td>
          <td>To comply with applicable laws, regulations, and legal processes</td>
        </tr>
      </tbody>
    </table>

    <h2>4. How We Share Your Information</h2>
    <p>We do not sell, rent, or trade your personal information to third parties. We may share your information in the following limited circumstances:</p>
    <ul>
      <li><strong>Service Providers:</strong> We may share information with trusted third-party service providers who assist us in operating the Application, provided they agree to keep your information confidential.</li>
      <li><strong>Legal Obligations:</strong> We may disclose information if required to do so by law, regulation, legal process, or governmental request.</li>
      <li><strong>Protection of Rights:</strong> We may disclose information to protect our rights, property, or safety, or that of our users or the public.</li>
      <li><strong>Business Transfers:</strong> In the event of a merger, acquisition, or sale of assets, your information may be transferred as part of that transaction. We will notify you of any such change.</li>
      <li><strong>With Your Consent:</strong> We may share your information with third parties when you give us explicit consent to do so.</li>
    </ul>

    <h2>5. Data Storage and Security</h2>
    <p>We take the security of your personal information seriously and implement appropriate technical and organizational measures to protect it, including:</p>
    <ul>
      <li>Encryption of data in transit and at rest</li>
      <li>Secure credential storage using industry-standard encryption</li>
      <li>Regular security assessments and updates</li>
      <li>Access controls limiting who can view personal information</li>
    </ul>
    <p>However, no method of transmission over the Internet or method of electronic storage is 100% secure. While we strive to use commercially acceptable means to protect your personal information, we cannot guarantee its absolute security.</p>

    <h2>6. Data Retention</h2>
    <p>We retain your personal information only for as long as necessary to fulfill the purposes for which it was collected, including to satisfy any legal, accounting, or reporting requirements. When your data is no longer needed, we will securely delete or anonymize it.</p>
    <p>You may request deletion of your data at any time by contacting us at the email address provided below.</p>

    <h2>7. Your Rights and Choices</h2>
    <p>Depending on your jurisdiction, you may have the following rights regarding your personal information:</p>
    <ul>
      <li><strong>Access:</strong> Request a copy of the personal information we hold about you.</li>
      <li><strong>Correction:</strong> Request correction of any inaccurate or incomplete information.</li>
      <li><strong>Deletion:</strong> Request deletion of your personal information, subject to certain legal exceptions.</li>
      <li><strong>Data Portability:</strong> Request a copy of your data in a structured, commonly used, machine-readable format.</li>
      <li><strong>Opt-Out:</strong> Opt out of certain data collection or processing activities.</li>
      <li><strong>Withdraw Consent:</strong> Where processing is based on consent, withdraw that consent at any time.</li>
    </ul>
    <p>To exercise any of these rights, please contact us using the information provided in Section 12. We will respond to your request within a reasonable timeframe and in accordance with applicable law.</p>

    <h2>8. Canadian Privacy Rights</h2>
    <p>If you are a resident of Canada, your personal information is protected under the Personal Information Protection and Electronic Documents Act (PIPEDA) and applicable provincial privacy laws. In addition to the rights above, you have the right to:</p>
    <ul>
      <li>Be informed of the purposes for which your information is collected at or before the time of collection</li>
      <li>Challenge the accuracy and completeness of your personal information and have it amended as appropriate</li>
      <li>File a complaint with the Office of the Privacy Commissioner of Canada if you believe your privacy rights have been violated</li>
    </ul>

    <h2>9. Children&rsquo;s Privacy</h2>
    <p>The Application is not intended for use by individuals under the age of 18. We do not knowingly collect personal information from children. If we become aware that we have collected personal information from a child under 18, we will take steps to delete that information promptly. If you believe a child has provided us with personal information, please contact us immediately.</p>

    <h2>10. Third-Party Links and Services</h2>
    <p>The Application may contain links to or interact with third-party websites and services that are not owned or controlled by us. We are not responsible for the privacy practices of these third parties. We encourage you to review the privacy policies of any third-party services you access through the Application.</p>

    <h2>11. Changes to This Privacy Policy</h2>
    <p>We may update this Privacy Policy from time to time to reflect changes in our practices or for other operational, legal, or regulatory reasons. We will notify you of any material changes by posting the new Privacy Policy within the Application with an updated effective date. Your continued use of the Application after changes are posted constitutes your acceptance of the revised policy.</p>

    <h2>12. Contact Information</h2>
    <p>If you have any questions, concerns, or requests regarding this Privacy Policy or our data practices, please contact us at:</p>
    <div class="contact-block">
      <p><strong>Name:</strong> Derek Kemle</p>
      <p><strong>Email:</strong> dereklawrencekemle@icloud.com</p>
    </div>
  </main>

  <footer>
    &copy; 2026 Derek Kemle. All rights reserved.
  </footer>
</body>
</html>
`;

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Response headers
    const headers = {
      'Content-Type': 'text/html;charset=UTF-8',
      'Cache-Control': 'public, max-age=3600',
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'strict-origin-when-cross-origin',
    };

    if (path === '/terms' || path === '/terms/') {
      return new Response(TERMS_HTML, { status: 200, headers });
    }

    if (path === '/privacy' || path === '/privacy/') {
      return new Response(PRIVACY_HTML, { status: 200, headers });
    }

    // Redirect root to terms or return 404
    if (path === '/' || path === '') {
      return Response.redirect(url.origin + '/terms', 302);
    }

    return new Response('Not Found', { status: 404, headers: { 'Content-Type': 'text/plain' } });
  },
};
