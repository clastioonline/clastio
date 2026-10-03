export type TeacherGuide = {
  slug: string; title: string; description: string; answer: string;
  sections: { heading: string; text: string }[]; steps: string[];
  example: string; questions: { question: string; answer: string }[];
};

export const teacherGuides: TeacherGuide[] = [
  {
    slug: "ai-ppt-maker-for-teachers-uae", title: "AI PPT maker for teachers in the UAE",
    description: "Create editable teaching presentations from your own materials, discuss the lesson first, and choose uploaded, licensed or AI images with Clastio.",
    answer: "Clastio helps teachers plan a lesson before generating an editable PowerPoint. Start with your topic, grade and learning goals, attach your teaching sources, choose your design and review the lesson sequence before building slides.",
    sections: [
      {heading: "Start with the learning problem", text: "A good presentation begins with what students should understand or do, rather than a slide count alone. State their prior knowledge, the misconception you want to address and the check you will use at the end. In the PPT playground, discuss these details before approving a draft."},
      {heading: "Use your own materials and design", text: "Select the textbook chapter or teaching notes that should ground the lesson. Upload an existing presentation as a design reference when your school uses a particular style. Check the generated examples, explanations and success criteria against the material you actually teach."},
      {heading: "Choose how the images are sourced", text: "Upload up to five relevant pictures with captions, or use Hybrid to search licensed images before AI fallback. Stock-only avoids paid image generation. When an exact photograph or scientific diagram matters, provide the image yourself and explain where it belongs."},
      {heading: "Review before the classroom", text: "Check quantities in diagrams, quiz answers, readability and lesson timing. Edit a single slide when a small correction is needed. PowerPoint exports remain editable, so you can finish the presentation in your usual teaching workflow."},
    ],
    steps: ["Specify topic, grade, subject and curriculum.", "Discuss goals and student needs in the playground.", "Attach the relevant book chapter or notes.", "Choose a design and image source.", "Review the chapter plan, then generate selected lessons.", "Check the slides and export an editable PPTX."],
    example: "Plan one Grade 6 science lesson on evaporation. Students confuse boiling with evaporation. Use an everyday UAE example, one demonstration and an exit ticket. Ask me about the class before drafting.",
    questions: [{question: "Can I use my own pictures?", answer: "Yes. Upload PNG, JPEG or WebP images in New chapter, add captions and use the slide editor for exact replacements."}, {question: "Does the assistant generate immediately?", answer: "The playground discusses the requirements and creates a reviewable brief. You decide when to create the chapter plan and build lessons."}, {question: "Is a trial available?", answer: "Clastio offers a seven-day trial with limited generation allowances. Check the pricing page for current plan details."}],
  },
  {
    slug: "lesson-planning-for-uae-teachers", title: "Lesson planning for UAE teachers",
    description: "Plan connected lessons, classroom activities and checks for understanding using your curriculum, class context and uploaded teaching sources.",
    answer: "Use Clastio to turn a chapter into a connected sequence of lessons, then adapt that sequence to your actual teaching time, prior learning and class needs. The teacher reviews the plan before slides are generated.",
    sections: [
      {heading: "Plan around available teaching time", text: "Tell the assistant how long the class lasts and how many lessons you have. A shorter timetable calls for fewer new ideas and a clear check for understanding. Give the actual school schedule rather than relying on assumed holiday or term dates."},
      {heading: "Connect new learning to prior learning", text: "State what the class has already covered and what still needs revision. Add the relevant textbook pages or notes. Review which concepts each lesson introduces and how later lessons retrieve earlier material, so the sequence does not repeat the same introduction."},
      {heading: "Differentiate with a purpose", text: "Specify the support students need using aggregate class information: simpler vocabulary, visual models, worked examples or additional challenge. Do not enter individual student names or sensitive records. Decide how the activity will help the whole class meet the learning goal."},
      {heading: "Reflect after teaching", text: "Record what went well, which ideas students struggled with and where you stopped. Use the next lesson's revision and previous-learning fields to carry these observations into planning. Keep remembered preferences up to date when your classroom needs change."},
    ],
    steps: ["Choose the chapter and curriculum.", "State lesson duration and available sessions.", "Add prior learning and areas to revise.", "Review objectives, activities and assessment.", "Build only the lessons you need next.", "Record a reflection and adapt the following lesson."],
    example: "We have three 35-minute lessons on fractions. The class can identify halves and quarters but struggles to compare denominators. Plan a connected sequence with visual models and quick checks.",
    questions: [{question: "Can I plan first and generate later?", answer: "Yes. Turn off automatic generation and review the chapter plan before building lessons."}, {question: "Can I generate only part of a chapter?", answer: "Yes. Use the chapter's selected-parts workflow to build the lessons you choose."}, {question: "Will the plan know my school's calendar?", answer: "Provide the actual dates and teaching time. The assistant should clarify missing details rather than assume your school's timetable."}],
  },
  {
    slug: "eal-lessons-uae", title: "Plan EAL-friendly lessons for UAE classrooms",
    description: "Use vocabulary support, visual explanations and structured classroom tasks to make your teaching presentations clearer for EAL learners.",
    answer: "For an EAL-friendly presentation, keep the subject goal clear while reducing unnecessary language demands. Ask Clastio for explicit vocabulary, visual explanations, sentence frames and checks that distinguish language difficulty from a misconception.",
    sections: [
      {heading: "Clarify the language demand", text: "Explain what language students need for the task: naming a process, comparing two ideas or explaining cause and effect. State the class's aggregate language needs. Simple English should make the explanation clearer while retaining the essential subject vocabulary."},
      {heading: "Teach vocabulary in context", text: "Select a small set of important words and use them in a worked example. Request bilingual vocabulary only when you can check the translation and it serves your class. Ask students to use the words in a sentence or explanation rather than copy a long glossary."},
      {heading: "Make visuals teach something", text: "A picture should explain the concept, not just decorate a slide. Provide your own diagram when exact labels, quantities or scientific relationships matter. Describe the image's purpose so the assistant can place it alongside the right explanation."},
      {heading: "Check understanding in more than one way", text: "Use a labelled sketch, sorting task or short oral explanation as well as a written response. Ask for common wrong answers and a teacher follow-up question. Review whether a response reveals a subject misconception or a difficulty expressing the answer."},
    ],
    steps: ["State the subject objective and class language needs.", "Choose essential vocabulary.", "Request a visual model and sentence frames.", "Include a worked example and guided practice.", "Add a check with more than one response format.", "Review the language and any translations before teaching."],
    example: "Grade 7 science: explain diffusion. Use clear English, define concentration, add a visual comparison and sentence frames. Keep the science accurate and ask what my students already know.",
    questions: [{question: "Will simpler language lower the subject goal?", answer: "It should not. Keep the learning objective explicit and review whether the simplification preserves the subject meaning."}, {question: "Can I save language preferences?", answer: "Yes. Add a confirmed language-level preference in Teacher memory and change it when your class needs change."}, {question: "Can I include bilingual vocabulary?", answer: "You can request it and save a preference, but review the translations before classroom use."}],
  },
  {
    slug: "british-curriculum-lesson-planning", title: "British curriculum lesson planning in the UAE",
    description: "Create a reviewable British curriculum lesson sequence from your teaching objectives and source material, with editable slides and assessment tasks.",
    answer: "Choose the British curriculum in your teaching profile, then supply the actual objectives, grade or year group, topic and school materials. Clastio helps draft the lesson sequence; the teacher checks it against the school's scheme of work.",
    sections: [
      {heading: "Specify the curriculum detail", text: "British curriculum is a starting point, not a complete specification. Tell the assistant the year group, subject and relevant programme or examination specification when needed. Do not assume that a grade number alone identifies your school's expectations."},
      {heading: "Turn objectives into evidence", text: "For each lesson objective, decide what students should be able to demonstrate by the end. Request success criteria, a worked example and a check for understanding. Review whether the activities produce evidence of learning rather than merely cover the topic."},
      {heading: "Use the school's source material", text: "Attach the textbook pages, teacher notes or existing lesson that should guide the content. Name the relevant section. This helps the assistant use the right terminology and prevents a generic presentation from substituting for the school's intended sequence."},
      {heading: "Adapt the lesson for your class", text: "Use teacher memory for confirmed language and presentation preferences, and state any exceptions in the current request. Specify retrieval, support and challenge requirements. Review question difficulty and any assessment wording before sharing it with students."},
    ],
    steps: ["Set the curriculum and year group.", "State the exact learning objectives.", "Attach the relevant school materials.", "Discuss prior knowledge and class needs.", "Review the sequence and assessment checks.", "Generate and verify the selected lessons."],
    example: "Plan a Year 8 chemistry lesson on conservation of mass using the uploaded notes. Include one worked example, a misconception check and a short exit ticket. Ask me which specification and practical resources apply.",
    questions: [{question: "Does Clastio certify curriculum alignment?", answer: "The teacher reviews the plan against the actual school objectives and specification. Generated material is a draft, not curriculum certification."}, {question: "Can I use an existing school presentation design?", answer: "Yes. Upload an existing deck as a design reference and review the resulting layouts."}, {question: "Can I change only one example?", answer: "Yes. Use the single-slide AI editor or make a manual edit instead of rebuilding the complete lesson."}],
  },
  {
    slug: "cbse-lesson-planning-uae", title: "CBSE lesson planning for teachers in the UAE",
    description: "Draft CBSE chapter lessons from your textbook and teaching notes, with worked examples, classroom activities and editable PowerPoint slides.",
    answer: "Set CBSE in your teaching profile and attach the relevant textbook chapter or notes. Discuss the grade, chapter section, learning goals and prior knowledge before reviewing a connected lesson plan and generating editable slides.",
    sections: [
      {heading: "Ground the lesson in the chapter", text: "Name the textbook, edition or chapter section that applies to your class and upload the relevant pages. Chapter names and grade levels can vary between materials. Use the actual source rather than asking the assistant to reconstruct a whole textbook from memory."},
      {heading: "Plan examples before practice", text: "For a maths or science lesson, request a worked example, guided practice and an independent check. Ask the assistant to explain the likely misconception and the teacher question that will reveal it. Verify calculations, units and answer keys before teaching."},
      {heading: "Use local examples when they help", text: "A UAE context can make an example familiar without replacing the curriculum concept. Describe the setting you want, such as a water-use comparison or a shopping calculation, and provide the numerical data. Avoid invented statistics or an unnecessary local reference on every slide."},
      {heading: "Build and revise selectively", text: "Review the chapter plan before spending credits on all lessons. Generate the parts you need next, then use slide-level changes for corrections. Record recurring preferences in Teacher memory so future drafts start closer to your preferred language and structure."},
    ],
    steps: ["Choose CBSE, subject and grade.", "Upload the relevant chapter section.", "State objectives and previously taught material.", "Discuss examples, activities and checks.", "Review the chapter plan.", "Build selected lessons and verify answers."],
    example: "Grade 8 mathematics: linear equations in one variable. Use the uploaded chapter section, show a balanced-equation worked example and include a short independent check. Ask me how much of the chapter is already taught.",
    questions: [{question: "Can I use textbook pages as a source?", answer: "Yes. Upload the relevant source and select it for the chapter, using material you have permission to use."}, {question: "Are generated answer keys automatically correct?", answer: "Review calculations and answers against your teaching material before classroom use."}, {question: "Can I keep the school slide design?", answer: "Upload an existing presentation as a design reference, then review the generated deck."}],
  },
  {
    slug: "edit-ppt-without-regenerating", title: "Edit a teaching PPT without regenerating every slide",
    description: "Make manual corrections, rewrite one slide or discuss an image replacement to reduce wasted generation credits on teaching presentations.",
    answer: "For a small correction, use the slide editor. Manual content changes and version restores use no generation credits. An AI rewrite targets one slide at the configured slide rate, while a complete lesson rebuild charges for the whole lesson's slide count.",
    sections: [
      {heading: "Match the edit to the problem", text: "Correct a typo, replace an exact photograph, change timing or select a layout manually. Use an AI slide rewrite when you need a clearer explanation, another example or a different classroom activity. Reserve full rebuilds for a substantial change to the topic or lesson approach."},
      {heading: "Combine related changes", text: "State everything you want changed on the selected slide in one instruction. Describe what must stay, especially the example, image and scientific meaning. Repeated short requests can consume more credits than one clear, reviewed instruction."},
      {heading: "Clarify image changes first", text: "Choose Discuss image changes from the slide editor. Explain what is wrong and what should be preserved, then choose licensed search or an AI replacement. Review the replacement brief before confirming. For an exact picture, upload it directly."},
      {heading: "Use history instead of paying for undo", text: "Review the updated slide and restore a previous version if needed. Existing images are kept by default during text rewrites. The editor displays the current configured cost, and duplicate pending requests reuse the current update job."},
    ],
    steps: ["Open the lesson and select the affected slide.", "Use manual editing for a precise correction.", "For an AI rewrite, combine changes into one instruction.", "Keep existing images unless the visual is the problem.", "Review the changed slide.", "Restore a prior version if you prefer it."],
    example: "This slide only: shorten the explanation to three bullets, keep the image and worked example, and move the detailed explanation to speaker notes.",
    questions: [{question: "Are manual changes free of generation credits?", answer: "Yes. Manual edits and version restores rebuild the export without charging generation credits."}, {question: "Does a single-slide edit rewrite the whole PPT?", answer: "The AI rewrite targets the selected slide. The export is rendered again so you receive an updated presentation."}, {question: "What if no replacement image is available?", answer: "The confirmed image-change workflow keeps the original and uses no generation credits for an unavailable replacement. AI provider costs or image allowance may still apply if a generated image was obtained before a later export failure."}],
  },
  {
    slug: "personal-ai-teaching-assistant", title: "A personal AI teaching assistant with teacher memory",
    description: "Save confirmed teaching preferences, discuss missing lesson details and keep control of what Clastio remembers for future presentations.",
    answer: "Clastio uses your teaching profile, confirmed preferences and relevant notes to personalise planning. A current request overrides a remembered preference. Learned suggestions need confirmation, and missing lesson or image requirements should become questions rather than assumptions.",
    sections: [
      {heading: "Remember reusable preferences", text: "Save preferences that apply across lessons, such as language level, image style, explanation depth or a recap at the beginning. A one-off request should remain specific to that lesson. Use Teacher memory to see which preferences you stated and which are still unconfirmed suggestions."},
      {heading: "Ask about the meaningful gaps", text: "The assistant should avoid asking again for information already in confirmed memory. It still needs the topic, learning goals and any changed classroom requirements. In an image discussion, what should change and what must stay are more useful than a vague request to make the image better."},
      {heading: "Keep preferences current", text: "A preference for one teaching group may not suit another. Change or remove a saved preference when needed, and state exceptions in the current request. Describe class needs in aggregate; avoid entering individual students' sensitive information."},
      {heading: "Learn with teacher control", text: "The slide editor can suggest a preference after repeated shortening of text, but that suggestion needs confirmation before it guides generation. When confirming an image replacement, optionally remember its style and source for later PPTs. You can delete those preferences in Teacher memory."},
    ],
    steps: ["Complete your teaching profile.", "Add reusable preferences in Teacher memory.", "Confirm useful learned suggestions.", "Discuss the current lesson in the playground.", "State exceptions to your usual preferences.", "Review or delete memories as needs change."],
    example: "Remember that I prefer diagrams for future lessons. For this presentation, use my uploaded photograph instead and ask me which details need highlighting.",
    questions: [{question: "Does a one-off image request change my preferences?", answer: "No. You can explicitly ask to remember a supported preference or choose the remember option after an image replacement."}, {question: "Can I delete a memory?", answer: "Yes. Teacher memory lets you remove preferences and stored notes."}, {question: "Will the assistant apply unconfirmed guesses?", answer: "Unconfirmed preferences are treated as suggestions to clarify, rather than defaults for generation."}],
  },
{
  "slug": "worksheet-maker-for-uae-teachers",
  "title": "Worksheet maker for UAE teachers",
  "description": "Create practice worksheets from your lesson and uploaded sources, with clear instructions, worked examples and a teacher-reviewed answer key.",
  "answer": "Create the lesson first, then use its document tools to draft a worksheet that practises the same objective. Describe the question types, difficulty and time available, and check the answer key before giving it to students.",
  "sections": [
    {
      "heading": "Choose what students should practise",
      "text": "State one or two learning goals and the skill each question should reveal. A worksheet on equivalent fractions should require students to recognise and construct equivalent fractions, rather than spend most of the time copying definitions. Specify the grade, prior learning and available working time."
    },
    {
      "heading": "Build support into the task",
      "text": "Request a worked example, guided questions and independent practice. For learners who need language support, use short instructions and a small vocabulary bank. For additional challenge, ask students to explain an error or justify a method rather than simply complete more questions."
    },
    {
      "heading": "Check the answers and format",
      "text": "Read every question alongside its answer. Check units, calculations, diagrams and any question with multiple valid responses. Download the resource and inspect spacing before printing. When an exact image matters, supply an approved picture and its source instead of requesting a decorative generated visual."
    }
  ],
  "steps": [
    "Open a lesson with the right learning objective.",
    "Choose a worksheet from the lesson documents.",
    "Specify question types, support and working time.",
    "Review questions against the source material.",
    "Check the answer key and downloaded layout."
  ],
  "example": "Draft a 15-minute Grade 6 worksheet on equivalent fractions from this lesson: one worked example, six practice questions and two explain-your-reasoning questions. Include an answer key and flag anything that needs a diagram.",
  "questions": [
    {
      "question": "Does a worksheet use credits?",
      "answer": "Document generation uses the worksheet rate shown in the app. Slides and AI images have separate allowances; check the current estimate before generating."
    },
    {
      "question": "Can I make separate support and challenge tasks?",
      "answer": "Specify the tasks and the learning goal in the document instruction. Review that both versions assess the same core concept."
    }
  ]
},
{
  "slug": "quiz-and-exit-ticket-maker",
  "title": "Create quizzes and exit tickets for teaching lessons",
  "description": "Draft short checks for understanding, useful distractors and answer explanations from your teaching sources with Clastio.",
  "answer": "Use a quiz or exit ticket to find out what students understood, not just what they can repeat. Give Clastio the lesson objective, the misconception to test and the response format, then verify each question and answer.",
  "sections": [
    {
      "heading": "Ask questions that reveal the misconception",
      "text": "For a lesson on evaporation, a question should distinguish evaporation from boiling. Ask for a wrong answer a student might plausibly choose and an explanation of why it is wrong. Avoid ambiguous wording that tests reading difficulty rather than the science."
    },
    {
      "heading": "Keep the check short enough to use",
      "text": "Specify the time available and how students will respond. Three carefully chosen questions may be more useful at the end of a lesson than a long quiz you cannot review. Mix a recall question, an application question and a short explanation when that fits the objective."
    },
    {
      "heading": "Plan what you will do with the answers",
      "text": "Ask for a follow-up teaching question or a next-lesson retrieval prompt. After class, record the aggregate difficulty in your reflection without student names. Use that information when planning revision; do not assume that a single wrong response proves a student has not learned the topic."
    }
  ],
  "steps": [
    "Choose the lesson objective and misconception.",
    "Specify question count, time and response format.",
    "Draft the quiz from the lesson document tools.",
    "Verify the correct answers and distractors.",
    "Use the results to plan the next lesson."
  ],
  "example": "Create a five-minute exit ticket for this lesson on evaporation: one multiple-choice misconception check, one everyday application and one explanation. Give the answer and the next question I should ask if students confuse evaporation with boiling.",
  "questions": [
    {
      "question": "Are AI answer keys guaranteed correct?",
      "answer": "No. Check every key, calculation and explanation against your source material before teaching."
    },
    {
      "question": "Can I save a preferred quiz length?",
      "answer": "Add a confirmed quiz-length preference in Teacher memory, and state any exception in the current request."
    }
  ]
},
{
  "slug": "differentiated-lesson-presentations",
  "title": "Differentiate lesson presentations without starting again",
  "description": "Adapt explanations, vocabulary, examples and practice for mixed-attainment classrooms while preserving the same learning goal.",
  "answer": "Start with a shared lesson objective, then describe the support and challenge your class needs. Clastio can help revise individual slides and activities so you can adapt a presentation without rebuilding the whole deck.",
  "sections": [
    {
      "heading": "Describe the barrier precisely",
      "text": "Explain whether learners need help with vocabulary, prior knowledge, reading load or a particular method. Use aggregate class information. A request for simpler slides is less useful than saying students can identify the numerator but confuse its role when comparing fractions."
    },
    {
      "heading": "Vary the support while keeping the goal",
      "text": "Ask for a visual model, a worked example or sentence frames for guided practice. Add a reasoning task for learners ready to go further. Review that the support helps students reach the lesson objective and that the extension does not introduce an unrelated topic."
    },
    {
      "heading": "Edit the affected slide",
      "text": "Combine the changes in one slide instruction and state what must stay. Keep a useful picture and the core example while shortening the explanation. Make exact corrections manually, or restore a previous version when it worked better. Save reusable preferences only when they apply across lessons."
    }
  ],
  "steps": [
    "State the common learning objective.",
    "Describe support and challenge needs.",
    "Choose the slide or activity that needs adaptation.",
    "Combine changes into one clear instruction.",
    "Review and compare the revised version."
  ],
  "example": "On this slide, keep the worked example and diagram. Add a sentence frame for explaining the method, reduce the introductory text to two bullets, and put one challenge question in the teacher notes.",
  "questions": [
    {
      "question": "Should I upload student records?",
      "answer": "Use aggregate class needs and avoid individual student names or sensitive records."
    },
    {
      "question": "Must I regenerate the whole presentation?",
      "answer": "No. Manual edits and single-slide AI rewrites let you adapt the affected slide. The app shows the current generation cost."
    }
  ]
},
{
  "slug": "turn-teaching-notes-into-powerpoint",
  "title": "Turn teaching notes and textbook sources into PowerPoint",
  "description": "Ground an editable teaching PPT in the chapter, PDF or notes you actually use, with a reviewable plan before slide generation.",
  "answer": "Upload the relevant teaching source, select it for your chapter and discuss the lesson goals before generating slides. Give the assistant the section that matters and verify that the plan covers it at the depth your class needs.",
  "sections": [
    {
      "heading": "Select the useful source, not every file",
      "text": "Use the chapter pages or notes that directly support this lesson. Name the chapter section and the learning goals. Scanned pages should be readable; inspect the uploaded material if labels, equations or small print are important. Use materials you have permission to upload."
    },
    {
      "heading": "Make the teaching sequence explicit",
      "text": "Tell the playground what has already been taught, which idea needs a worked example and how you will check understanding. The source provides grounding, while the teacher decides how the class should learn it. Review the chapter plan before generating selected lessons."
    },
    {
      "heading": "Review source-specific details",
      "text": "Check terminology, worked calculations, quantities in diagrams and any passage that the assistant has summarised. A source upload does not guarantee that every sentence or image will be reproduced exactly. Upload an exact visual or make a manual correction when fidelity matters."
    }
  ],
  "steps": [
    "Upload readable, relevant teaching materials.",
    "Select the source for the chapter.",
    "State topic, grade, curriculum and objectives.",
    "Discuss prior learning and lesson duration.",
    "Review the sequence, then generate selected lessons.",
    "Verify important details against the source."
  ],
  "example": "Use the uploaded chapter section on the water cycle to plan two Grade 5 lessons. The class already knows evaporation. Focus on condensation and collection, include a local everyday example, and ask me which practical resources are available.",
  "questions": [
    {
      "question": "Can I upload a whole textbook?",
      "answer": "Use the relevant material within the app upload limits and your permission to use it. Selecting the right chapter section makes review easier."
    },
    {
      "question": "Does upload guarantee exact content?",
      "answer": "No. Review the generated explanation, numbers and labels against your source before classroom use."
    }
  ]
},
{
  "slug": "reuse-school-powerpoint-design",
  "title": "Reuse your school PowerPoint design for teaching slides",
  "description": "Use an existing presentation as a design reference and keep a reusable teacher style for future editable lesson decks.",
  "answer": "Upload an existing PowerPoint as a design reference, save the resulting style and select it when creating a chapter. Review the generated layouts before teaching, especially when your school requires particular fonts, spacing or brand assets.",
  "sections": [
    {
      "heading": "Choose a representative reference",
      "text": "Use a deck with the layouts you actually teach with: title, explanation, example and practice. A reference with consistent typography and spacing is easier to use than a collection of unrelated designs. Keep a copy of the original and use materials your school permits you to share."
    },
    {
      "heading": "Review readability rather than appearance alone",
      "text": "Check heading size, contrast and how much text fits on a projected slide. Explain whether the class needs large labels, short explanations or visual examples. A design should support the teaching objective and work with the actual classroom display."
    },
    {
      "heading": "Reuse and adjust selectively",
      "text": "Save a preferred style for future chapters and choose a different one when a lesson needs it. The generated deck is an editable draft rather than a guaranteed pixel-perfect copy. Use the manual slide editor or PowerPoint for exact placement and inspect the exported file before class."
    }
  ],
  "steps": [
    "Choose an approved, consistent reference deck.",
    "Upload it as a design reference.",
    "Review and save the teacher style.",
    "Select that style for the chapter.",
    "Check the export and make exact adjustments."
  ],
  "example": "Use my uploaded presentation as the design reference. Keep explanations brief, prefer a worked-example layout for mathematics, and ask me which school elements must be included before planning.",
  "questions": [
    {
      "question": "Is the result an exact copy of the reference?",
      "answer": "It is a design-guided editable draft. Review layouts and use manual editing for exact school requirements."
    },
    {
      "question": "How many styles can I save?",
      "answer": "Style-profile allowances depend on your current plan. The pricing page and usage screen show the current limits."
    }
  ]
},
{
  "slug": "stock-images-for-teaching-presentations",
  "title": "Use uploaded and licensed stock images in teaching PPTs",
  "description": "Choose stock-only or hybrid image sourcing, provide your own diagrams, and reduce paid AI-image calls in teaching presentations.",
  "answer": "Use stock-only when suitable licensed visuals are enough, Hybrid when you want search before AI fallback, or upload an exact diagram yourself. Describe what the visual must teach and review both accuracy and attribution.",
  "sections": [
    {
      "heading": "Choose the source for the teaching task",
      "text": "Stock-only searches licensed images without paid AI-image generation. Hybrid searches first and can generate a fallback within your allowance. AI mode requests generated visuals directly. A recognisable real-world photograph often works well as stock; an exact labelled diagram may be better supplied by the teacher."
    },
    {
      "heading": "Explain what belongs in the picture",
      "text": "Give the subject, relevant details and the purpose of the visual. Add captions to teacher uploads so the system can place them with the appropriate slide. Check whether scientific quantities, labels and relationships are correct, especially in generated illustrations."
    },
    {
      "heading": "Replace one visual with a reviewed brief",
      "text": "If a picture is wrong, discuss the selected slide with the image assistant. Say what should change and what must stay, then review the source and replacement brief before confirming. For an exact replacement, upload the picture in the manual editor. Check any licence and attribution requirements for your intended use."
    }
  ],
  "steps": [
    "Decide whether you need an exact visual or a general illustration.",
    "Upload your approved picture or select stock-only/Hybrid.",
    "Describe the subject and teaching purpose.",
    "Review accuracy and source attribution.",
    "Use the image discussion for a targeted replacement."
  ],
  "example": "For this slide use a licensed photograph of a leaf, not an AI illustration. Keep the explanation unchanged. Ask me whether the image needs labels and offer stock-only search before preparing a replacement.",
  "questions": [
    {
      "question": "Does stock-only spend AI-image allowance?",
      "answer": "Stock-only avoids paid AI-image generation. Lesson generation and discussion can still use content-generation credits and provider tokens."
    },
    {
      "question": "Can I supply my own image?",
      "answer": "Yes. New chapter accepts up to five PNG, JPEG or WebP images with captions; the manual slide editor supports exact replacements."
    }
  ]
},
];

export function findTeacherGuide(slug: string) {
  // Validate bounded route input and then require an exact allowlisted guide.
  return slug.length <= 80 && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug) ? teacherGuides.find((guide) => guide.slug === slug) : undefined;
}
