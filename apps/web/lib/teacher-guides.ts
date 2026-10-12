export type TeacherGuide = {
  slug: string; title: string; description: string; answer: string;
  category?: string; reviewedAt?: string; relatedSlugs?: string[];
  sources?: { label: string; url: string; note?: string }[];
  sections: { id?: string; heading: string; text: string; checks?: string[];
    table?: { caption: string; columns: string[]; rows: string[][] } }[]; steps: string[];
  example: string; questions: { question: string; answer: string }[];
};

export const teacherGuides: TeacherGuide[] = [
  {
    "slug": "ai-ppt-maker-for-teachers-uae",
    "title": "AI PowerPoint maker for teachers in the UAE",
    "description": "Create an editable lesson PPT from your objectives and teaching sources. Review the first lesson, reuse a school design, and check slides before class.",
    "answer": "Clastio drafts editable lesson PowerPoints from a teacher’s topic, class context and selected teaching sources. Set the learning objective first, review the chapter plan, build one lesson and check it before approving the next. You can use a school design, supplied pictures and targeted slide edits to finish the teaching presentation.",
    "sections": [
      {
        "heading": "What to give an AI lesson presentation maker",
        "text": "A useful brief describes what learners must be able to do and the evidence you want to collect. In a British curriculum school, include the actual year group and programme or examination specification when relevant. Your teaching profile controls the subjects and grades offered in New chapter; update it if your timetable changes.",
        "checks": [
          "Name the topic, subject, year group and lesson duration.",
          "Paste the learning objective and any curriculum codes you are authorised to use.",
          "Describe prior knowledge and one misconception to address.",
          "Identify the book chapter, PDF pages or notes that should guide the explanation.",
          "Describe class support needs in aggregate, without student names or records."
        ]
      },
      {
        "id": "abu-dhabi-lesson-slides",
        "heading": "Create lesson slides for an Abu Dhabi classroom",
        "text": "For slide creation in Abu Dhabi, start with the programme your school follows, the subject and the actual year group. Select the source pages and state what learners should demonstrate before choosing a layout. ADEK publishes curriculum and teaching-resource policies for schools; check the current guidance with your curriculum lead. A city name alone does not identify a syllabus, class language level or lesson duration. Clastio helps draft the presentation from the teaching context you provide.",
        "checks": [
          "Confirm the school programme, year group and current learning objective.",
          "Select readable notes or textbook pages you have permission to use.",
          "Describe class language support and available equipment without student records.",
          "Use a local example only when it explains the concept, and check its facts.",
          "Review the first lesson, move or edit a supported object, and test the exported PPTX before class."
        ]
      },
      {
        "id": "british-or-moe",
        "heading": "Choose the British or UAE MoE teaching context",
        "text": "British curriculum planning and UAE Ministry of Education curriculum planning need different source documents. UAE MoE subjects can also form part of a school's wider programme: adding a local example does not make a British science lesson a MoE curriculum lesson. Confirm the programme and subject requirements with the school, then choose the matching teaching profile and sources. Use the Ministry's official resources for current MoE materials; Clastio is independent teaching software.",
        "table": {
          "caption": "Supply the documents for the lesson you actually teach",
          "columns": ["Teaching context", "Brief and source material", "Review before slides"],
          "rows": [
            ["British programme", "Actual year group, school scheme of work, and examination specification where relevant.", "Use only the supplied objectives and approved codes."],
            ["UAE MoE programme", "Current grade, school-approved MoE textbook or notes, and the selected chapter.", "Check the applicable edition, subject and teaching sequence."],
            ["MoE subject within another school programme", "State both the school programme and the subject requirements confirmed by the curriculum lead.", "Check the required content and source instead of inferring it from the city or a generic label."]
          ]
        }
      },
      {
        "heading": "A lesson sequence before a slide design",
        "text": "Review the chapter outline to check that each lesson introduces a useful next step. Build the first PPT, inspect its explanation and practice, then approve the current version before continuing. After teaching, record what needs revision so the next lesson responds to the class.",
        "table": {
          "caption": "Example review framework for a single science lesson",
          "columns": [
            "Teaching purpose",
            "What a slide should do",
            "Evidence to review"
          ],
          "rows": [
            [
              "Retrieve",
              "Ask a short question about prior learning.",
              "The answer and follow-up question are in the teacher notes."
            ],
            [
              "Explain",
              "Model one new idea using the relevant source.",
              "Terminology and the visual match the objective."
            ],
            [
              "Practise",
              "Give a guided task before independent work.",
              "The task has a checked answer or success criteria."
            ],
            [
              "Check",
              "Use a quiz or exit ticket.",
              "The response tells you what to revisit next lesson."
            ]
          ]
        }
      },
      {
        "heading": "Reuse a school PPT design and choose images deliberately",
        "text": "Upload an approved deck as a design reference, or choose a ready design. Inspect how explanations, worked examples and practice fit the layouts. Supply exact diagrams yourself when quantities and labels matter. Stock-only searches licensed visuals without paid AI-image generation; Hybrid can use AI fallback within your allowance. Review image accuracy and attribution either way."
      },
      {
        "heading": "Check the downloaded PowerPoint, then make a targeted correction",
        "text": "Open the PPTX in the presentation software you will use in class. Change one text box, move a picture and inspect the speaker notes. In Clastio, use Edit PPT for object changes and Save & rebuild to update the exports. A PDF is useful for sharing or printing; it is not a substitute for checking the editable PPTX.",
        "checks": [
          "Compare definitions, calculations, diagram labels and answer keys with the source.",
          "Check reading size and contrast on the actual classroom display.",
          "Correct a typo or object position manually; use a single-slide AI rewrite for a teaching-content change.",
          "If an edit changes the approved lesson, review the current version again before building the next."
        ]
      }
    ],
    "steps": [
      "Choose your teaching subject, grade, curriculum and topic.",
      "Attach the relevant source pages and state the objective.",
      "Discuss duration, prior knowledge and class needs in the playground.",
      "Review the chapter plan and choose a presentation design.",
      "Build and check the first lesson, then approve its current version.",
      "Export PPTX and prepare the next lesson after review."
    ],
    "example": "Plan a 40-minute Year 8 science lesson on diffusion for a British curriculum school in the UAE. Use my selected notes and supplied outcomes only. Learners confuse particle movement with changes in particle size. Include retrieval, a checked visual explanation, guided practice and an exit question with an expected answer. Ask about missing practical resources before drafting.",
    "questions": [
      {
        "question": "Is Clastio an official MoE UAE or ADEK service?",
        "answer": "Clastio is independent teaching software. The UAE Ministry of Education and ADEK publish their own official resources and school policies. Linking those sources does not imply their endorsement; the teacher supplies the relevant objectives and checks the lesson against the school's requirements."
      },
      {
        "question": "Does an AI PowerPoint maker verify curriculum alignment?",
        "answer": "You provide the programme, objectives and approved codes, and review the output against the scheme of work. Clastio drafts the lesson and retains supplied outcome codes; it does not certify a curriculum or exam-board endorsement."
      },
      {
        "question": "Can I edit the PowerPoint objects or only the text?",
        "answer": "Use the PPT editor to select and move supported objects, or finish the downloaded PPTX in PowerPoint. Save & rebuild refreshes the exported files. Editing a downloaded PDF as if it were a PowerPoint is a different workflow."
      },
      {
        "question": "Can I use my own textbook and school design?",
        "answer": "Yes. Select teaching material you have permission to upload, choose the relevant page range and use an approved deck as a design reference. Check that the explanation follows the material and the layout stays readable."
      },
      {
        "question": "Is the teacher PPT maker free to try?",
        "answer": "New accounts start on Free. Generation is limited by the current plan allowances; an eligible trial is a separate choice. Check the pricing page and the generation estimate before building a lesson."
      }
    ],
    "category": "Presentations",
    "reviewedAt": "2026-10-12",
    "sources": [
      {
        "label": "ADEK: School Curriculum Policy",
        "url": "https://www.adek.gov.ae/-/media/Project/TAMM/ADEK/Policies/School-Policies/Teaching-and-Learning/ADEK_S_Curriculum-Policy_EN_v1_2.pdf",
        "note": "Official school curriculum guidance. Confirm the policy and subject requirements that apply to your school."
      },
      {
        "label": "UAE Ministry of Education: Minhaji",
        "url": "https://minhaji.moe.gov.ae/",
        "note": "Official textbook platform; access and permitted use are governed by the publisher's requirements."
      },
      {
        "label": "Microsoft Support: PowerPoint file formats",
        "url": "https://support.microsoft.com/en-us/powerpoint/file-formats-that-are-supported-in-powerpoint",
        "note": "PPTX can also contain picture-based slides; test whether the objects you need to change are editable."
      },
      {
        "label": "British Council: Using AI safely and responsibly in teaching",
        "url": "https://africa.teachingenglish.org.uk/skills/tips/ai-safe-responsible-use",
        "note": "Review generated teaching material and avoid sharing identifiable learner information."
      }
    ],
    "relatedSlugs": [
      "british-curriculum-lesson-planning",
      "turn-teaching-notes-into-powerpoint",
      "reuse-school-powerpoint-design",
      "ai-lesson-planning-costs-and-credits"
    ]
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
    "slug": "british-curriculum-lesson-planning",
    "title": "British curriculum lesson planning in the UAE",
    "description": "Plan a British curriculum lesson in the UAE using the actual year group, scheme of work, supplied outcomes and source pages before building editable slides.",
    "answer": "Start with the school’s programme and year group, then identify what learners should demonstrate by the end of the lesson. If the class is preparing for GCSE or IGCSE, include the examination board, subject code and examination year. Clastio helps draft a sequence and editable presentation from the objectives and sources you supply; the teacher checks the match to the school’s scheme of work.",
    "sections": [
      {
        "heading": "Which British curriculum details belong in the brief?",
        "text": "The phrase British curriculum does not identify a complete lesson specification. England’s National Curriculum publishes programmes of study by key stage. A GCSE or IGCSE course also needs the relevant qualification and subject specification. Use the documents your school actually follows and check how its year-group labels map to the app’s grade field.",
        "table": {
          "caption": "Choose the reference that answers the planning question",
          "columns": [
            "Planning context",
            "Useful reference",
            "Teacher supplies"
          ],
          "rows": [
            [
              "Primary or lower secondary",
              "The school scheme of work and applicable programme of study.",
              "Year group, prior learning and lesson objective."
            ],
            [
              "GCSE course",
              "The actual examination board specification and subject content.",
              "Board, subject code, exam year and tier where applicable."
            ],
            [
              "IGCSE course",
              "The selected awarding organisation’s subject syllabus.",
              "Qualification, syllabus code, exam year and route where applicable."
            ]
          ]
        }
      },
      {
        "heading": "Make the objective observable",
        "text": "Choose an outcome you can see in learners’ work. For an illustrative lesson about explaining a process, a useful check could ask pupils to order the stages and justify one link. State the expected reasoning before asking for slides. This helps distinguish an explanation, a practice task and an assessment question instead of repeating the same topic heading.",
        "checks": [
          "Objective: what will the learner explain, calculate, compare or demonstrate?",
          "Teaching example: what model or worked answer makes the idea clear?",
          "Practice: what can learners attempt with gradually reduced support?",
          "Check: what response would show understanding, and what error would you follow up?"
        ]
      },
      {
        "heading": "Keep source coverage separate from curriculum labels",
        "text": "Attach the relevant school notes or authorised textbook pages. Include the supplied outcome text and codes; ask the assistant to leave unspecified codes blank. A source page supports the explanation, while a curriculum code identifies an intended outcome. Review both: a plausible page reference does not prove that the question difficulty or practical activity fits your specification."
      },
      {
        "heading": "Adapt a lesson to a UAE classroom without changing the core goal",
        "text": "Describe language support, prior knowledge and available equipment using class-level information. A familiar local context is useful when it explains the concept; provide any numerical data it needs. Review translations, examples and practical instructions. Avoid relying on an assumed school calendar or treating every class in the same city as having identical needs."
      },
      {
        "heading": "Review one lesson before continuing the chapter",
        "text": "Check the chapter outline, then build the first PPT. Review its sources, examples, notes and answer keys, and approve the current presentation version before the next lesson. Record what learners struggled with and use the next lesson’s previous-learning and revision fields to carry that evidence forward."
      }
    ],
    "steps": [
      "Confirm programme, year group and the school scheme of work.",
      "For an examination course, add board, subject code, exam year and route.",
      "Supply the learning objective, approved codes and source pages.",
      "Plan an explanation, guided practice and a check with an expected answer.",
      "Review the first presentation and approve its current version.",
      "Use teaching reflection to prepare the next lesson."
    ],
    "example": "Prepare one Year 8 chemistry lesson using my selected school notes. Objective: explain why the total mass in a closed chemical reaction is conserved. Use only the outcomes I supply. Include one illustrated explanation, guided reasoning and a short check with expected answers. Confirm our programme, available equipment and prior learning before drafting; use no invented exam-board references.",
    "questions": [
      {
        "question": "Are GCSE and IGCSE the same lesson specification?",
        "answer": "Use the actual course documents. Cambridge describes IGCSE standards as aligned with GCSE, but this does not identify your school’s subject syllabus, assessment route or examination year. Check those details before choosing content and questions."
      },
      {
        "question": "Does selecting British automatically identify my school’s year group?",
        "answer": "No. Supply the actual school year group and confirm how your school uses the app’s grade field. The class profile and current brief should describe the group you teach."
      },
      {
        "question": "Can the app invent missing curriculum codes?",
        "answer": "Supply the codes approved for the request. Clastio retains supplied codes rather than creating new alignment codes. If you have only an objective description, include that text and review the result against your documents."
      },
      {
        "question": "Can a familiar UAE example replace the syllabus material?",
        "answer": "Use the local example to explain the intended concept. Keep the objective, terminology and required skill tied to the school’s scheme of work; provide and check any example data."
      }
    ],
    "category": "British curriculum",
    "reviewedAt": "2026-10-12",
    "sources": [
      {
        "label": "Department for Education: National curriculum for England",
        "url": "https://www.gov.uk/government/collections/national-curriculum",
        "note": "Use the programme of study relevant to your school; check the actual scheme of work."
      },
      {
        "label": "Department for Education: GCSE subject content",
        "url": "https://www.gov.uk/government/collections/gcse-subject-content",
        "note": "Subject content is a starting reference. Your examination board specification supplies the course detail."
      },
      {
        "label": "Cambridge International: Cambridge IGCSE",
        "url": "https://www.cambridgeinternational.org/programmes-and-qualifications/cambridge-upper-secondary/cambridge-igcse/",
        "note": "An official introduction to the qualification and subject routes."
      }
    ],
    "relatedSlugs": [
      "gcse-igcse-lesson-presentations",
      "turn-teaching-notes-into-powerpoint",
      "eal-lessons-uae",
      "quiz-and-exit-ticket-maker"
    ]
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
    "title": "Turn a textbook PDF or teaching notes into an editable PowerPoint",
    "description": "Choose chapter pages, check readable source material, then turn a textbook PDF or teaching notes into a reviewed lesson plan and editable PPTX.",
    "answer": "Upload an authorised textbook PDF or teaching notes, select the relevant chapter pages, and state what the class should learn. Review source readiness and the proposed lesson sequence before building a PPTX. The source grounds the draft; you still check quotations, equations, diagrams and answers against the original material.",
    "sections": [
      {
        "heading": "Choose the chapter section that supports the objective",
        "text": "A whole book can contain material the class does not need yet. In Books & notes, identify the title, edition and relevant chapter; in New chapter, select the source and physical PDF page range. Printed textbook page numbers can differ from PDF page positions, so compare them before relying on a reference.",
        "checks": [
          "Use material you have permission to upload and process.",
          "Confirm subject, year group, edition and chapter title.",
          "Check the selected PDF pages include any definitions, examples and diagrams needed for the objective.",
          "Keep unrelated chapters out of the brief and note any missing source material."
        ]
      },
      {
        "heading": "Check text PDFs, scans and exact diagrams differently",
        "text": "A text PDF may provide extractable text directly. Scanned pages need readable images and a configured ingestion model; service limits still apply. If extraction misses small labels, symbols or equations, provide an OCR/text version or checked typed notes. Supply an exact diagram as an image when it must appear with specific labels or quantities.",
        "table": {
          "caption": "A quick source-readiness check before slide generation",
          "columns": [
            "Material",
            "Check before planning",
            "If the detail is missing"
          ],
          "rows": [
            [
              "Textbook PDF",
              "The chapter text and page range are readable.",
              "Select the correct pages or add a checked note."
            ],
            [
              "Scanned PDF",
              "The scan is legible and indexing finishes successfully.",
              "Provide an OCR/text PDF or clearer pages."
            ],
            [
              "Teacher notes",
              "Definitions, examples and intended sequence are explicit.",
              "Add the omitted worked answer or prerequisite."
            ],
            [
              "Exact diagram",
              "Labels and relationships match what you teach.",
              "Upload the approved image with a caption."
            ]
          ]
        }
      },
      {
        "heading": "Use the source to explain, practise and check",
        "text": "Ask for a teaching sequence rather than a page-by-page copy. Name the idea to explain, the worked example to use, the practice learners will attempt and the answer you will check. Keep a note of which source supports each part. If the material lacks a mark scheme or a particular worked calculation, request teacher review rather than presenting it as verified textbook content."
      },
      {
        "heading": "Review coverage warnings before exporting the PPTX",
        "text": "Compare the plan with the selected pages and check any source-coverage warnings. Then inspect definitions, numerical answers, units and diagram labels in the first generated lesson. Use manual corrections or a single-slide rewrite for a specific issue. Approve the current presentation only after review before preparing the next lesson.",
        "checks": [
          "Can you find the important claim in the source you selected?",
          "Are page references physical PDF pages or printed page labels?",
          "Does the practice require only knowledge already taught?",
          "Are worked answers and quiz explanations checked?",
          "Does the downloaded PPTX remain editable in your classroom software?"
        ]
      }
    ],
    "steps": [
      "Upload the authorised source and confirm indexing is ready.",
      "Select the relevant chapter and physical PDF page range.",
      "State the objective, year group, duration and prior learning.",
      "Request an explanation, practice and a check grounded in the selected material.",
      "Review source coverage and build the first presentation.",
      "Verify the export against the source before approving the next lesson."
    ],
    "example": "Use only the selected PDF pages for this 35-minute Year 7 lesson. The class already knows evaporation; focus on explaining condensation. Identify the source for the definition and the diagram, include guided practice and give a checked exit answer. Flag missing source coverage and ask me before adding an unsupported textbook reference.",
    "questions": [
      {
        "question": "Can I turn a scanned textbook PDF into PowerPoint?",
        "answer": "Readable scans can be ingested when the required live ingestion model is configured and the file fits the service limits. Wait for the source to be ready. If indexing fails or symbols are unclear, use an OCR/text version or checked notes."
      },
      {
        "question": "Will every PDF object become an editable PowerPoint object?",
        "answer": "A generated lesson PPTX is editable, but source text extraction is not a promise to convert every original PDF object exactly. Supply exact visuals when needed and inspect the downloaded presentation."
      },
      {
        "question": "Does adding a textbook verify every fact and answer?",
        "answer": "No. Compare the generated material with the selected pages, especially calculations, labels, question difficulty and any source-coverage warning. The teacher remains responsible for the final classroom resource."
      },
      {
        "question": "Do I need to upload the same source for every lesson?",
        "answer": "Use the saved source and select its relevant pages for the chapter. Keep edition and chapter metadata current; reuse does not remove the need to check which pages apply to the next objective."
      }
    ],
    "category": "Teaching sources",
    "reviewedAt": "2026-10-12",
    "sources": [
      {
        "label": "Microsoft Support: PowerPoint file formats",
        "url": "https://support.microsoft.com/en-us/powerpoint/file-formats-that-are-supported-in-powerpoint",
        "note": "PPTX can also contain picture-based slides; test whether the objects you need to change are editable."
      },
      {
        "label": "British Council: Using AI safely and responsibly in teaching",
        "url": "https://africa.teachingenglish.org.uk/skills/tips/ai-safe-responsible-use",
        "note": "Review generated teaching material and avoid sharing identifiable learner information."
      }
    ],
    "relatedSlugs": [
      "british-curriculum-lesson-planning",
      "ai-ppt-maker-for-teachers-uae",
      "stock-images-for-teaching-presentations",
      "edit-ppt-without-regenerating"
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
  {
    "slug": "how-to-choose-ai-presentation-maker-for-teachers",
    "title": "How to choose an AI presentation maker for teachers",
    "description": "Compare lesson quality, source handling, editable PPTX exports and total preparation cost using the same classroom task and a practical download test.",
    "category": "Choosing a tool",
    "reviewedAt": "2026-10-12",
    "answer": "Compare tools using one lesson objective and the same source material. Check whether the output teaches the objective, whether you can edit the downloaded PPTX, and how much time and allowance it takes to reach a classroom-ready result. A polished preview alone does not answer those questions.",
    "sections": [
      {
        "heading": "Run the same teaching task in each tool",
        "text": "Choose a small lesson you already know well: one objective, a readable source section and a fixed duration. State prior learning, a common misconception, one practice task and an expected exit answer. Keep that brief consistent so a difference in output is not simply a difference in your instructions. Record the changes you need to make before teaching."
      },
      {
        "heading": "A teacher’s comparison checklist",
        "text": "Ask for evidence you can inspect in a real result. Some tools focus on attractive presentations; others support lesson sequences, source grounding or classroom resources. Prioritise the tasks you repeat rather than a feature list you may never use.",
        "table": {
          "caption": "Compare evidence from the same lesson task",
          "columns": [
            "Criterion",
            "Inspect in the result",
            "Test to try"
          ],
          "rows": [
            [
              "Learning objective",
              "The example, practice and check address the same skill.",
              "Ask what the exit response would demonstrate."
            ],
            [
              "Source use",
              "Important claims can be checked against your material.",
              "Look up one definition and one worked answer."
            ],
            [
              "PPTX editing",
              "Text and pictures you need to change are editable.",
              "Download, change a text box and move a picture."
            ],
            [
              "Design reuse",
              "The layout stays readable with your lesson content.",
              "Try an approved school deck and a dense example."
            ],
            [
              "Total cost",
              "Planning, slides, edits and images are accounted for.",
              "Record the estimates and the allowance used."
            ],
            [
              "School suitability",
              "Uploads and class context fit school requirements.",
              "Review policies and use aggregate learner needs."
            ]
          ]
        }
      },
      {
        "heading": "Perform the PowerPoint download test",
        "text": "Open the exported file in the software and on the device you will use in class. Microsoft documents several PowerPoint formats, including a picture-based PPTX format. The extension alone therefore does not prove that individual objects are editable. Check the objects you actually need to change.",
        "checks": [
          "Rewrite one sentence and change its font size.",
          "Move or replace a picture without moving the whole slide.",
          "Inspect speaker notes, equations, fonts and slide order.",
          "Run Slide Show and compare it with the web preview.",
          "Save the edited file and reopen it."
        ]
      },
      {
        "heading": "Measure preparation effort rather than a promised time saving",
        "text": "Record the time to prepare the brief, check the answers, fix the layout and export the lesson. Count correction types such as a wrong unit, missing prerequisite or unreadable label. Compare that work with your current process. A faster draft may still need careful review, and one successful topic does not prove that every subject will work equally well."
      },
      {
        "heading": "Compare plans after checking the useful output",
        "text": "Read the current allowances for slides, documents, AI rewrites, images and storage. Check trial eligibility, final checkout price and renewal terms. In Clastio, a new account starts on Free; an eligible trial is chosen separately. Use the displayed generation estimate for the actual lesson you plan to build."
      }
    ],
    "steps": [
      "Choose one objective, source section and lesson duration.",
      "Use the same brief when evaluating each tool.",
      "Check source use, worked answers and learner practice.",
      "Download the presentation and test individual object edits.",
      "Record review time and the total allowance used.",
      "Compare current plans against the teaching tasks you repeat."
    ],
    "example": "Create a 35-minute lesson from these authorised notes for the year group I specify. Teach one objective, address this misconception, include a worked example and guided practice, and provide an exit question with its expected answer. Use a readable school design and supply an editable PPTX with speaker notes. Ask about missing information before building.",
    "questions": [
      {
        "question": "What is the best AI presentation maker for teachers?",
        "answer": "The useful choice depends on your subject, school sources, export workflow and budget. Use the same classroom task and inspect the actual download before choosing. A ranking or a polished screenshot does not replace that test."
      },
      {
        "question": "Is a PDF export enough if I want to move slide objects?",
        "answer": "Check a PPTX export when individual slide objects need to be edited in PowerPoint. PDF is useful for sharing and printing, but it serves a different workflow."
      },
      {
        "question": "Should I choose a tool that promises automatic curriculum alignment?",
        "answer": "Check what evidence it provides for your actual programme and specification. Supply the objectives and approved codes, and review examples and questions against the course documents."
      },
      {
        "question": "Can I compare Clastio without buying a paid plan first?",
        "answer": "Start on Free and check the current generation allowances. If an eligible trial is available, you can choose it separately. Use the pricing page and in-app estimate to decide which sample task fits the allowance."
      }
    ],
    "sources": [
      {
        "label": "Microsoft Support: PowerPoint file formats",
        "url": "https://support.microsoft.com/en-us/powerpoint/file-formats-that-are-supported-in-powerpoint",
        "note": "PPTX can also contain picture-based slides; test whether the objects you need to change are editable."
      },
      {
        "label": "British Council: Using AI safely and responsibly in teaching",
        "url": "https://africa.teachingenglish.org.uk/skills/tips/ai-safe-responsible-use",
        "note": "Review generated teaching material and avoid sharing identifiable learner information."
      }
    ],
    "relatedSlugs": [
      "ai-ppt-maker-for-teachers-uae",
      "reuse-school-powerpoint-design",
      "edit-ppt-without-regenerating",
      "ai-lesson-planning-costs-and-credits"
    ]
  },
  {
    "slug": "gcse-igcse-lesson-presentations",
    "title": "Plan GCSE and IGCSE lesson presentations from the right specification",
    "description": "Identify the qualification, exam board, subject code and examination year before drafting a GCSE or IGCSE lesson PPT from supplied objectives and sources.",
    "category": "British curriculum",
    "reviewedAt": "2026-10-12",
    "answer": "A GCSE or IGCSE lesson brief needs more than “Year 10 science”. Identify the qualification, examination board, subject code, examination year and any relevant tier or route. Supply the intended outcomes and source section, then connect the explanation, practice and assessment to that same objective before building slides.",
    "sections": [
      {
        "heading": "Confirm the qualification and the version of its documents",
        "text": "Cambridge describes IGCSE standards as aligned with GCSE, while providing subject-specific syllabuses. England’s Department for Education also publishes GCSE subject content. Neither reference alone identifies the exact course your class is taking. Use the examination board and subject specification that your school follows, with the edition or examination year stated."
      },
      {
        "heading": "The brief to complete before generating an exam-course PPT",
        "text": "Copy course details from your actual documents. When an item does not apply, say so; when it is unknown, clarify it before generating questions. In Cambridge’s Physics 0625 example, the syllabus year identifies the year of examination, so the current school year alone is not enough to select the correct document.",
        "table": {
          "caption": "Teacher-supplied specification details",
          "columns": [
            "Detail",
            "Why it changes the lesson",
            "What to supply"
          ],
          "rows": [
            [
              "Qualification and board",
              "Names the course and authority for its requirements.",
              "Your school’s actual GCSE or IGCSE qualification."
            ],
            [
              "Subject and code",
              "Separates subjects and syllabus variants.",
              "The identifier copied from the specification."
            ],
            [
              "Examination year",
              "Selects the applicable syllabus edition.",
              "The year your class will take the examination."
            ],
            [
              "Tier or route",
              "Can change required depth or paper requirements.",
              "The route relevant to your class, where applicable."
            ],
            [
              "Outcome and source",
              "Connects the lesson to teaching evidence.",
              "Supplied codes/text and the relevant source section."
            ]
          ]
        }
      },
      {
        "heading": "Connect a syllabus outcome to a teaching sequence",
        "text": "Choose a manageable outcome, then decide what explanation makes it understandable and what response would show learning. For an illustrative calculation lesson, this could be a model with units, a guided question and an independent variation. Only include an equation, question type or practical requirement after checking that it belongs in the supplied specification.",
        "checks": [
          "Keep the supplied outcome code and wording intact.",
          "Identify the prerequisite that the starter should retrieve.",
          "Check the worked answer, units and reasoning against your source.",
          "Reduce support during practice without introducing untaught material.",
          "Choose an exit response that tests the same outcome."
        ]
      },
      {
        "heading": "Use exam-style questions with clear provenance",
        "text": "If using an actual board question, follow the source’s permissions and preserve the details needed to identify it. If asking AI for a new practice question, label it as generated practice and review the answer and mark allocation. Do not present an invented question or mark scheme as an official past-paper item. Give the assistant an authorised worked answer when a precise method matters."
      },
      {
        "heading": "Keep the first lesson reviewable",
        "text": "Attach the relevant source pages, choose the school design and build the first PPT. Compare its content with the supplied outcome, inspect the notes and answer keys, and approve the current version before the next lesson. If source coverage is incomplete, resolve the gap rather than using plausible-looking references as evidence."
      }
    ],
    "steps": [
      "Confirm qualification, board, subject code, examination year and route.",
      "Select the applicable specification and authorised source section.",
      "Paste the intended outcome text and approved codes.",
      "Plan retrieval, explanation, guided practice and an independent check.",
      "Review question provenance, answers, units and depth.",
      "Inspect and approve the first presentation before building the next."
    ],
    "example": "Prepare one 40-minute lesson for our examination course. Qualification and board: [school course]. Subject code: [verified code]. Exam year and route: [class details]. Objective and permitted codes: [paste from our documents]. Sources: [selected pages]. Use an explanation, a checked worked example, guided practice and an exit question. Flag gaps; label any new AI-written practice question clearly.",
    "questions": [
      {
        "question": "Can one Year 10 PPT be used for every GCSE and IGCSE course?",
        "answer": "Check the actual course, subject specification and class needs first. Similar topics can have different required depth, question formats or practical expectations. Adapt the material to the documents your school follows."
      },
      {
        "question": "Does a syllabus year mean the school year I am currently teaching?",
        "answer": "Check the awarding organisation’s definition. Cambridge’s Physics 0625 page states that the syllabus year is the year the examination will be taken. Use the relevant examination-year document for that course."
      },
      {
        "question": "Will Clastio create an official exam-board mark scheme?",
        "answer": "Generated practice and suggested answers need teacher review. Provide authorised official material when you need its exact method or marking guidance, and keep generated questions distinct from official items."
      },
      {
        "question": "What if I have an outcome description but no alignment code?",
        "answer": "Supply the outcome text and source section. Leave missing codes unspecified; do not invent an identifier to make the lesson appear aligned."
      }
    ],
    "sources": [
      {
        "label": "Department for Education: GCSE subject content",
        "url": "https://www.gov.uk/government/collections/gcse-subject-content",
        "note": "Subject content is a starting reference. Your examination board specification supplies the course detail."
      },
      {
        "label": "Cambridge International: Cambridge IGCSE",
        "url": "https://www.cambridgeinternational.org/programmes-and-qualifications/cambridge-upper-secondary/cambridge-igcse/",
        "note": "An official introduction to the qualification and subject routes."
      },
      {
        "label": "Cambridge IGCSE Physics 0625: syllabus and resources",
        "url": "https://www.cambridgeinternational.org/programmes-and-qualifications/cambridge-igcse-physics-0625/",
        "note": "Choose the syllabus for the examination year. This is an example subject reference, not the specification for every science class."
      }
    ],
    "relatedSlugs": [
      "british-curriculum-lesson-planning",
      "turn-teaching-notes-into-powerpoint",
      "quiz-and-exit-ticket-maker",
      "differentiated-lesson-presentations"
    ]
  },
  {
    "slug": "ai-lesson-planning-costs-and-credits",
    "title": "Estimate AI lesson planning costs and presentation credits",
    "description": "Estimate planning, slides, worksheets, quizzes, AI edits and image allowances using current rates, with a clearly labelled example calculation.",
    "category": "Planning costs",
    "reviewedAt": "2026-10-12",
    "answer": "Estimate the whole teaching task: chapter planning, the slides actually generated, classroom documents and any AI edits. Check image allowances separately. Clastio shows current generation estimates and plan usage; use those values rather than assuming that a presentation count means unlimited slides or that a trial begins automatically.",
    "sections": [
      {
        "heading": "Start with the tasks your lesson needs",
        "text": "Count the first presentation you will prepare, its slide target and the supporting resources you actually need. A chapter plan and a lesson deck are different tasks. Build and review one lesson before approving the next so later decks are a deliberate decision rather than a budget assumption.",
        "checks": [
          "Chapter planning: check the current planning rate.",
          "Slides: multiply the actual slide count by the current slide rate.",
          "Documents: include any worksheet, quiz or lesson-plan generation you request.",
          "AI changes: add the single-slide or full-lesson action you intend to use.",
          "Images: check the separate AI-image allowance and selected source mode."
        ]
      },
      {
        "heading": "A worked credit estimate using assumed rates",
        "text": "For illustration only, assume planning costs 2 credits, each slide 1 credit, a quiz 3 credits and a worksheet 4 credits. A plan plus ten slides and one quiz would use 2 + (10 × 1) + 3 = 15 credits. Adding the worksheet makes 19. These are example assumptions, not a current price quote; replace them with the app’s displayed rates.",
        "table": {
          "caption": "Illustrative estimate only: replace all rates with the current values",
          "columns": [
            "Requested task",
            "Assumed calculation",
            "Example credits"
          ],
          "rows": [
            [
              "Chapter plan",
              "1 × 2",
              "2"
            ],
            [
              "Ten-slide presentation",
              "10 × 1",
              "10"
            ],
            [
              "One quiz",
              "1 × 3",
              "3"
            ],
            [
              "Optional worksheet",
              "1 × 4",
              "4"
            ],
            [
              "Plan + PPT + quiz",
              "2 + 10 + 3",
              "15"
            ],
            [
              "Including the worksheet",
              "15 + 4",
              "19"
            ]
          ]
        }
      },
      {
        "heading": "Understand reservations and flexible slide counts",
        "text": "When flexible slides are enabled, Clastio can reserve credits for up to three additional slides and charge for the actual slide count. As an illustrative slide-only example at an assumed rate of one credit per slide, a twelve-slide request can reserve for fifteen; an eleven-slide result uses eleven slide credits. The other requested tasks remain separate. Check available and reserved credits in Usage when work is queued."
      },
      {
        "heading": "Choose a correction that fits the problem",
        "text": "Manual corrections and version restores use no generation credits. A single-slide AI rewrite uses the configured slide rate, while rebuilding a whole lesson generates its slide count again. Combine related changes in one reviewed instruction and keep existing visuals when they are suitable. Stock-only avoids paid AI-image generation; it does not remove the credits used for generating lesson content."
      },
      {
        "heading": "Compare Free, a chosen trial and paid plans",
        "text": "New accounts start on Free. Eligible teachers can choose an available trial separately during onboarding or billing; check its current duration and allowances. Paid plans have their own credit, image and storage limits. Review current prices, billing periods, taxes and renewal terms on the pricing and checkout pages rather than treating this worked example as a subscription offer."
      }
    ],
    "steps": [
      "Choose the first lesson and the resources you need.",
      "Read the current planning, slide, document and edit rates.",
      "Calculate the task total using those values.",
      "Check any flexible-slide reservation and separate image allowance.",
      "Compare the estimate with available plan credits.",
      "Review the result and use a targeted correction where appropriate."
    ],
    "example": "Help me budget one chapter plan, one ten-slide first lesson and one quiz. Use the current rates displayed in my account, keep AI-image generation separate, and show the estimate before I confirm. I will review the first lesson before deciding to prepare the next.",
    "questions": [
      {
        "question": "How many credits does one teaching PPT use?",
        "answer": "Multiply the actual slides generated by the current slide rate, then add any chapter planning, documents or AI edits you request. Check the in-app estimate; a short presentation and a longer presentation need different totals."
      },
      {
        "question": "Do manual edits spend the same credits as AI rewrites?",
        "answer": "Manual edits and version restores do not use generation credits. AI rewrites are generation actions and use the current configured rate. Export rendering refreshes the file after an edit."
      },
      {
        "question": "Are AI images included in slide credits?",
        "answer": "Check the image allowance separately. Stock-only avoids paid AI-image calls; Hybrid can use AI fallback within the allowance. The lesson’s text and slide generation still have their own credit usage."
      },
      {
        "question": "Does signup automatically start the trial?",
        "answer": "No. Signup starts the account on Free. An eligible trial is a separate choice, and its current availability and allowances appear in onboarding or billing."
      },
      {
        "question": "Are the rates in the example guaranteed current?",
        "answer": "No. The worked calculation uses stated assumptions to show the method. The pricing page and your account’s estimate are the places to check current values before generating."
      }
    ],
    "sources": [
      {
        "label": "Clastio pricing and current plan allowances",
        "url": "/pricing",
        "note": "Check live plan details; your account shows current generation rates, estimates and remaining usage."
      }
    ],
    "relatedSlugs": [
      "how-to-choose-ai-presentation-maker-for-teachers",
      "edit-ppt-without-regenerating",
      "stock-images-for-teaching-presentations",
      "ai-ppt-maker-for-teachers-uae"
    ]
  },
];

export function findTeacherGuide(slug: string) {
  // Validate bounded route input and then require an exact allowlisted guide.
  return slug.length <= 80 && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug) ? teacherGuides.find((guide) => guide.slug === slug) : undefined;
}

const RELATED_GUIDES: Record<string, string[]> = {
  "lesson-planning-for-uae-teachers": ["british-curriculum-lesson-planning", "eal-lessons-uae", "quiz-and-exit-ticket-maker", "ai-lesson-planning-costs-and-credits"],
  "eal-lessons-uae": ["british-curriculum-lesson-planning", "differentiated-lesson-presentations", "worksheet-maker-for-uae-teachers", "personal-ai-teaching-assistant"],
  "cbse-lesson-planning-uae": ["turn-teaching-notes-into-powerpoint", "worksheet-maker-for-uae-teachers", "quiz-and-exit-ticket-maker", "ai-lesson-planning-costs-and-credits"],
  "edit-ppt-without-regenerating": ["reuse-school-powerpoint-design", "stock-images-for-teaching-presentations", "ai-lesson-planning-costs-and-credits", "how-to-choose-ai-presentation-maker-for-teachers"],
  "personal-ai-teaching-assistant": ["lesson-planning-for-uae-teachers", "eal-lessons-uae", "differentiated-lesson-presentations", "ai-ppt-maker-for-teachers-uae"],
  "worksheet-maker-for-uae-teachers": ["quiz-and-exit-ticket-maker", "differentiated-lesson-presentations", "british-curriculum-lesson-planning", "turn-teaching-notes-into-powerpoint"],
  "quiz-and-exit-ticket-maker": ["gcse-igcse-lesson-presentations", "british-curriculum-lesson-planning", "worksheet-maker-for-uae-teachers", "differentiated-lesson-presentations"],
  "differentiated-lesson-presentations": ["eal-lessons-uae", "worksheet-maker-for-uae-teachers", "edit-ppt-without-regenerating", "personal-ai-teaching-assistant"],
  "reuse-school-powerpoint-design": ["ai-ppt-maker-for-teachers-uae", "how-to-choose-ai-presentation-maker-for-teachers", "edit-ppt-without-regenerating", "stock-images-for-teaching-presentations"],
  "stock-images-for-teaching-presentations": ["turn-teaching-notes-into-powerpoint", "edit-ppt-without-regenerating", "reuse-school-powerpoint-design", "ai-lesson-planning-costs-and-credits"],
};

export function relatedTeacherGuides(guide: TeacherGuide): TeacherGuide[] {
  return (guide.relatedSlugs || RELATED_GUIDES[guide.slug] || [])
    .map(findTeacherGuide).filter((related): related is TeacherGuide => Boolean(related && related.slug !== guide.slug));
}
