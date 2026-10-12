export type SupportPage = {
  path: string; title: string; description: string; introduction: string;
  sections: { title: string; text: string; links?: { href: string; label: string }[] }[];
};

export const supportPages: SupportPage[] = [
  {
    path: "/help", title: "Clastio help centre", description: "Help with sign-in, lesson generation, editable PPT downloads, billing and privacy requests.",
    introduction: "Find a next step for the task you are working on. For an account-specific problem, open a support ticket or contact Clastio by email.",
    sections: [
      { title: "Sign-in and verification", text: "Use the sign-in method linked to your account. For an email/password account, request a fresh password-reset link if you cannot sign in. An expired verification link needs a new link; opening a success page does not verify an account.", links: [{ href: "/login", label: "Sign in" }, { href: "/forgot-password", label: "Reset your password" }, { href: "/session-expired", label: "Session help" }] },
      { title: "Planning or generation did not finish", text: "Check Activity for the saved job and its status before submitting again. If AI is paused or a provider is unavailable, saved resources remain available. Review source coverage, supplied outcome codes and the selected teaching profile before retrying a lesson.", links: [{ href: "/activity", label: "Open Activity" }, { href: "/status", label: "Check service status" }, { href: "/solutions/turn-teaching-notes-into-powerpoint", label: "Source-based lesson workflow" }] },
      { title: "Editing and downloading a presentation", text: "Download the PPTX when you need editable slide objects. A PDF is a viewing/export format and does not guarantee that every original object can be reconstructed for editing. Manual changes and targeted AI changes have different credit costs; inspect the current estimate before confirming generation.", links: [{ href: "/solutions/edit-ppt-without-regenerating", label: "Edit one slide" }, { href: "/solutions/how-to-choose-ai-presentation-maker-for-teachers", label: "Check an editable export" }] },
      { title: "Payments, plans and limits", text: "A checkout return is not proof that a payment succeeded. Your billing screen shows the provider-confirmed plan, any pending checkout and available recovery options. Check usage and queued reservations before generating more resources.", links: [{ href: "/billing", label: "Plan and billing" }, { href: "/pricing", label: "Current prices" }, { href: "/usage-limit", label: "Usage-limit help" }, { href: "/cancellation-policy", label: "Cancellation help" }] },
      { title: "Tell support what happened", text: "Include the page, approximate time, relevant job or request reference and the steps that led to the problem. Share a screenshot with personal information removed. Do not send passwords, API keys, payment-card details or identifying student records.", links: [{ href: "/contact", label: "Contact Clastio" }, { href: "/support", label: "Open an account support ticket" }] },
      { title: "Privacy and account requests", text: "Use Settings to review account details and available controls. The current account export is a summary; downloaded teaching files and a complete personal-data request are different things. Contact support for a broader request or a school data-processing review.", links: [{ href: "/data-privacy", label: "Privacy requests" }, { href: "/delete-account", label: "Request account deletion" }, { href: "/faq", label: "Product questions" }] },
    ],
  },
  {
    path: "/security", title: "Security and account protection", description: "Practical account, upload and payment security guidance for Clastio teachers and schools.",
    introduction: "Protect your sign-in details and use teaching materials your school permits you to upload. Contact Clastio if you suspect an account or content-access problem.",
    sections: [
      { title: "Account access", text: "Authenticated requests enforce account access and permissions. Keep your password private and review signed-in sessions in Settings. End an unfamiliar session and change your password if your account may be compromised.", links: [{ href: "/settings", label: "Account settings and sessions" }, { href: "/forgot-password", label: "Request a password reset" }] },
      { title: "Teaching files and AI processing", text: "Personal teaching resources require account access. AI generation sends the inputs needed for the selected task to configured providers. Use class needs in aggregate and avoid student names or sensitive records. Read the published privacy policy and ask about school requirements before uploading material.", links: [{ href: "/legal/privacy", label: "Published privacy policy" }, { href: "/data-processing", label: "School data-processing review" }] },
      { title: "Payment decisions", text: "Checkout and account billing use the configured payment partner. Confirm the total and payment method on that partner’s checkout. Clastio grants paid access after server-side payment confirmation; a page URL or a browser success message cannot grant a subscription.", links: [{ href: "/billing", label: "Review your plan" }, { href: "/pricing", label: "Compare plans" }] },
      { title: "Report a security concern", text: "Contact support with the affected page or resource reference, the time and a description of the issue. Do not include passwords, tokens or anyone else’s private files. Security enquiries are reviewed through the support channel.", links: [{ href: "/contact", label: "Contact support" }, { href: "/status", label: "Service status" }] },
    ],
  },
  {
    path: "/data-privacy", title: "Privacy and personal-data requests", description: "Find Clastio privacy information and request account access, corrections, exports or deletion.",
    introduction: "Read the current published policy, use the account controls available to you, or contact support for a personal-data request.",
    sections: [
      { title: "Read the published version", text: "The Privacy Policy explains the published data-handling terms. Policy history preserves earlier versions. For a question about AI processing, recipients or school requirements, contact support rather than assuming that all providers use identical retention settings.", links: [{ href: "/legal/privacy", label: "Privacy Policy" }, { href: "/legal/cookie", label: "Cookie Policy" }] },
      { title: "Access and correct account information", text: "Update your profile and teaching preferences in Settings. The available JSON account export contains profile and teaching-resource summaries; it does not contain every generated file, conversation or record. Download teaching files from their resource pages, and contact support if you need a broader personal-data export.", links: [{ href: "/settings", label: "Account settings" }, { href: "/data-export-request", label: "Data export request" }, { href: "/contact", label: "Request assistance" }] },
      { title: "Request account deletion", text: "The deletion workflow requires confirmation of your account email. A confirmed request disables access and schedules further account cleanup. A request receipt is different from confirmation that all retained records or files have been removed. Contact support about the request, retained records or cancelling a request during the available grace period.", links: [{ href: "/delete-account", label: "Account deletion workflow" }, { href: "/contact", label: "Contact about a privacy request" }] },
      { title: "Manage optional communications", text: "Review your marketing and notification choices in Settings. Important security, payment and policy notices can still be required. Avoid including sensitive personal information in a support ticket or email.", links: [{ href: "/notification-preferences", label: "Notification preferences" }, { href: "/email-unsubscribe", label: "Email preference help" }] },
    ],
  },
  {
    path: "/data-processing", title: "School data-processing requests", description: "Request a data-processing review or agreement for a proposed Clastio school pilot.",
    introduction: "Discuss your school’s requirements before a rollout. This page helps start a review; it is not an executed data-processing agreement.",
    sections: [
      { title: "Describe the planned use", text: "Tell support your school, the intended teaching workflow, the types of information involved and the procurement contact. Provide requirements in summary without attaching student records or confidential datasets.", links: [{ href: "/contact", label: "Start a school enquiry" }, { href: "/for-schools", label: "Plan a teacher-led pilot" }] },
      { title: "Agree on roles and processing", text: "Ask about the applicable controller/processor roles, selected providers, storage and transfer arrangements, retention and request handling. Any agreement must reflect the actual service and be agreed with the authorised parties; downloading or viewing this page creates no agreement.", links: [{ href: "/legal/privacy", label: "Published privacy information" }, { href: "/security", label: "Account and upload guidance" }] },
      { title: "Use an approved pilot", text: "Choose authorised teaching sources and school designs, describe learning needs in aggregate, and review output before classroom use. Confirm contractual and access requirements before wider use.", links: [{ href: "/solutions/reuse-school-powerpoint-design", label: "School design workflow" }, { href: "/legal/acceptable_use", label: "Acceptable Use Policy" }] },
    ],
  },
  {
    path: "/accessibility", title: "Accessibility support", description: "Accessibility features, practical assistance and reporting barriers in Clastio.",
    introduction: "Clastio uses responsive layouts, visible form labels and keyboard controls. Accessibility testing is ongoing; contact support if a page or task is difficult to use.",
    sections: [
      { title: "Keyboard and reading support", text: "Use Tab to move between controls and Enter or Space where a control supports activation. Public guides have headings and in-page links. Slide editing supports keyboard movement of selected objects; complex visual work may still need assistance.", links: [{ href: "/help", label: "Find help for a task" }, { href: "/solutions/edit-ppt-without-regenerating", label: "Slide editing workflow" }] },
      { title: "Report a barrier", text: "Tell support the page, task, browser/device and any assistive technology you use. Describe what you expected and what happened. Remove private information from screenshots and ask for an alternative way to complete the task when needed.", links: [{ href: "/contact", label: "Report an accessibility issue" }] },
      { title: "Review classroom exports", text: "Before sharing a presentation or worksheet, review readability, contrast, text size, language and the meaning of visual content. A generated export still needs teacher review for the learners who will use it.", links: [{ href: "/solutions/differentiated-lesson-presentations", label: "Adapt a teaching resource" }] },
    ],
  },
  {
    path: "/copyright", title: "Copyright and teaching-material enquiries", description: "Authorised uploads, textbook references and how to report a copyright concern to Clastio.",
    introduction: "Use sources and designs you are authorised to upload. A publisher link or a textbook reference does not grant permission to redistribute the book.",
    sections: [
      { title: "Before uploading or sharing", text: "Check the rights for your textbook pages, notes, pictures and presentation design. Permission for personal teaching use may differ from permission to share with every teacher. Preserve relevant source and image attribution.", links: [{ href: "/legal/acceptable_use", label: "Acceptable Use Policy" }, { href: "/solutions/turn-teaching-notes-into-powerpoint", label: "Use teaching sources" }] },
      { title: "Report a concern", text: "Email support with the material or page reference, a description of the work and your relationship to it, the basis of your concern and a way to contact you. Do not attach sensitive student information or unrelated private content. Support can request further information to review the report.", links: [{ href: "/contact", label: "Contact Clastio" }] },
      { title: "Book sources and generated resources", text: "The book-source catalogue includes publisher and official references as well as openly licensed sources. Commercial references are not a claim that the platform owns or can distribute every book. Review the source licence and generated content before classroom use.", links: [{ href: "/legal/terms", label: "Terms & Conditions" }, { href: "/help", label: "Help with a resource" }] },
    ],
  },
  {
    path: "/cancellation-policy", title: "Subscription cancellation and refund requests", description: "How to cancel a Clastio subscription, review billing status and request a refund under the published policy.",
    introduction: "Use account billing to manage a paid plan. Cancellation and a monetary refund are different actions.",
    sections: [
      { title: "Cancel future renewal", text: "For a supported recurring paid subscription, the billing workflow requests cancellation at the end of the paid period. Check the server-confirmed status in Plan & billing. A pending checkout or a manual/non-renewing grant can have a different recovery path.", links: [{ href: "/billing", label: "Manage plan and billing" }, { href: "/subscription-cancelled", label: "Review cancellation status" }] },
      { title: "Request a refund", text: "Read the current published Refund Policy and contact support with the payment reference, purchase date and reason for the request. Do not email full payment-card details. Support reviews requests against the policy and the payment provider’s records; visiting a page cannot issue or confirm a refund.", links: [{ href: "/legal/refund", label: "Published Refund Policy" }, { href: "/contact", label: "Contact about a refund" }] },
      { title: "Check access and allowances", text: "Use the billing and usage screens to check the current plan and available credits. A browser return or a query parameter is not proof of paid access, cancellation or a refund.", links: [{ href: "/pricing", label: "Current plans" }, { href: "/usage-limit", label: "Usage help" }, { href: "/legal/terms", label: "Terms & Conditions" }] },
    ],
  },
];
