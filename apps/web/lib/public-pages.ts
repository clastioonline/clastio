export const publicPages = [
  {
    path: "/how-it-works", title: "How Clastio turns your lesson idea into an editable PPT",
    description: "Discuss the lesson, use your teaching sources, review a plan, generate selected slides and make targeted changes with Clastio.",
    introduction: "Start with the learning goal. Your assistant helps clarify the lesson before you spend credits building a presentation, and you review the material before it reaches the classroom.",
    sections: [
      {heading: "1. Tell the assistant about your class", text: "Choose the subject, grade and curriculum, then describe the objective and prior learning. Confirm reusable preferences in Teacher memory. Current instructions override those preferences when this lesson needs something different."},
      {heading: "2. Bring your materials and design", text: "Select the relevant textbook pages or notes. Use an approved presentation as a design reference, and upload pictures with captions when you need exact visuals. Choose stock-only, Hybrid or AI for other images."},
      {heading: "3. Discuss and review the lesson plan", text: "Use the playground to decide duration, activities, explanations and checks for understanding. Review the brief and chapter sequence. Generate selected lessons when you are ready rather than building a whole chapter at once."},
      {heading: "4. Check the slides and classroom resources", text: "Review calculations, diagram quantities, language and answer keys. Use the lesson's document tools for worksheets and quizzes that support the same objective. Inspect the downloaded PPTX in your usual presentation software."},
      {heading: "5. Improve the part that needs work", text: "Correct a typo manually, rewrite one slide or discuss one image replacement. Combine related changes, state what must stay and confirm the image brief before replacement. Manual edits and version restores use no generation credits."},
    ],
    links: [{href: "/solutions/turn-teaching-notes-into-powerpoint", label: "Use your teaching sources"}, {href: "/solutions/edit-ppt-without-regenerating", label: "Make targeted changes"}],
  },
  {
    path: "/for-schools", title: "Explore Clastio for your school or department",
    description: "Plan a teacher-led pilot for reusable presentation designs, classroom resources and lesson planning with Clastio.",
    introduction: "Begin with a small pilot and the teaching work you want to improve. Evaluate lesson quality, preparation time and review effort before choosing a wider rollout.",
    sections: [
      {heading: "Pick a measurable teaching problem", text: "Choose a shared chapter, a presentation design or a recurring worksheet task. Record how teachers currently prepare it. During the pilot, compare preparation time, corrections needed and classroom usefulness rather than simply counting generated slides."},
      {heading: "Use approved school materials", text: "Start with teaching sources and reference decks your school permits teachers to upload. Describe class needs in aggregate. Check your school's data-handling requirements before uploading materials; individual student records are not needed to plan a lesson."},
      {heading: "Agree on a review routine", text: "Teachers should check objectives, calculations, images and answer keys before classroom use. Set a clear expectation for who reviews a shared resource, how corrections are recorded and when a source or design needs updating."},
      {heading: "Confirm the rollout requirements", text: "Check account access, plan allowances and any enabled integrations against what your school actually needs. Ask about procurement and billing arrangements before committing to a rollout. Individual plans and their current limits are shown on the pricing page."},
    ],
    links: [{href: "/pricing", label: "Review individual plans"}, {href: "/solutions/reuse-school-powerpoint-design", label: "Reuse an approved school design"}, {href: "/legal/privacy", label: "Read the privacy policy"}],
  },
  {
    path: "/faq", title: "Clastio questions: trials, credits, images and teacher memory",
    description: "Understand the seven-day trial, generation credits, uploaded images, editable PowerPoint exports and teacher-controlled memory.",
    introduction: "Find answers before you start, then check the pricing page and your usage screen for the current plan limits and generation estimates.",
    sections: [
      {heading: "How does the seven-day trial work?", text: "New accounts start on Free. Eligible teachers can choose to start a seven-day trial with limited generation allowances and no card required during onboarding or in Plan & billing. When the trial ends, the account returns to Free unless you subscribe. Check current trial credits and enabled features on the pricing page."},
      {heading: "How many PPTs can I create?", text: "Plans provide credits rather than a fixed number of unlimited-length presentations. At the default one-credit-per-slide rate, a ten-slide PPT uses ten credits; chapter planning, documents and AI edits use additional credits. AI images have a separate allowance. The app shows the current rates and remaining usage."},
      {heading: "Can I provide images or avoid AI-image generation?", text: "Yes. Upload up to five images with captions for a new chapter, or provide an exact replacement in the slide editor. Stock-only searches licensed visuals without paid AI-image calls. Hybrid searches first and can use AI fallback within your allowance."},
      {heading: "What happens when I need changes?", text: "Use manual editing for exact changes or an AI rewrite for one slide. For image changes, the assistant asks what should change, what should stay and which source you prefer. You review and confirm the replacement brief. An unavailable or identical replacement keeps the original without generation-credit charges."},
      {heading: "What does the assistant remember?", text: "Confirmed teaching preferences and relevant notes help personalise future planning. A current request overrides a saved preference. One-off image requests do not become permanent settings automatically; choose the remember option or explicitly ask to save a supported preference. Teacher memory lets you review and delete it."},
      {heading: "Are exports editable and answers verified?", text: "PowerPoint exports are editable. Generated explanations, diagrams and answer keys still need teacher review. The app does not certify curriculum alignment or guarantee any third-party AI detector result."},
      {heading: "Can I cancel a paid subscription?", text: "You can cancel through the billing workflow. Your paid access continues until the end of the billing period. Review the terms and refund policy for the applicable conditions, and check the checkout page for the final price, taxes and discounts."},
    ],
    links: [{href: "/pricing", label: "Current prices and allowances"}, {href: "/solutions/personal-ai-teaching-assistant", label: "Manage teacher memory"}, {href: "/legal/refund", label: "Refund policy"}],
  },
];
