LABELING_RUBRIC = """
Task: Label a single earnings-call sentence as either:
- boilerplate
- substantive

Definitions:
1) boilerplate
   Scripted introductions, operator instructions, safe-harbor text, replay/webcast/legal disclaimers, 
   analyst/speaker introductions, generic thanks or turn-taking language.

2) substantive
   Sentences containing material business content: numerical results, guidance, segment commentary, 
   strategy, demand/pricing discussion, capital allocation, risk commentary, operational specifics, 
   or substantive Q&A answers.

Guidance:
- Any question or explanation related to the company's business should be treated as substantive.
- Any mention that the company specifically did, launched, changed, delivered, achieved, invested in, or decided something should be treated as substantive.
- Any sentence that reveals the speaker's attitude toward a specific matter or person should be treated as substantive.
- Business-related questions in Q&A are substantive even if they contain conversational filler or hedging language.
- Pronoun-heavy sentences can be substantive when the pronoun clearly refers to a business topic, action, product, market, risk, customer behavior, strategy, financial metric, or prior Q&A point from nearby context.
- Transition sentences are substantive when they preview a specific business, financial, operational, product, customer, market, strategy, risk, or capital-allocation topic that will be discussed.
- Management views about past business events, execution, performance, mistakes, lessons learned, or market conditions are substantive.
- Statements about future determination, intent, plans, commitments, priorities, or actions are substantive when tied to the business, strategy, customers, operations, products, markets, risks, or financial outcomes.

Anchor examples of boilerplate:
- Good morning and welcome to the conference call.
- This call may contain forward-looking statements.
- Our next question comes from ...
- Thank you for joining us today.

Anchor examples of substantive:
- Revenue grew 12% year over year to $5.2 billion.
- We expect second-half margins to improve as utilization recovers.
- Demand in enterprise remained soft, but cloud bookings improved sequentially.
- That will be an important tailwind through the rest of the year.
- Those things should help us improve profitability over time.
- Now I will discuss our fourth quarter NII outlook.
- We learned from that experience and are changing how we serve those customers.
- We are committed to improving execution and investing behind that opportunity.

Edge-case rules:
- Analyst name intros are boilerplate.
- One-word answers like 'Yes' or 'No' are boilerplate unless surrounded by explicit material content.
- Mixed sentences: if a sentence contains clear material business information, label substantive.
- Sentences using pronouns or vague references such as "it", "this", "that", "they", "them", "those things", "the issue", or "the opportunity" are substantive if they carry a claim, expectation, risk, decision, cause, or implication about a business-related topic from context.
- Pronoun-only filler remains boilerplate if it does not convey business content (for example, "that is all I have" or "we will leave it there").
- High-level summaries of the company's performance are substantive if they describe the company's progress or performance, even without detailed numbers (for example, "we made significant progress over the past year").
- Reflections on past business outcomes are substantive if they state an assessment, lesson, cause, or implication (for example, "we could have executed better in that market" or "that decision positioned us well").
- Future-oriented statements are substantive if they express a business plan, commitment, priority, or intended action (for example, "we will keep investing in capacity" or "we are determined to improve service levels").
- Specific thanks or praise for a person's concrete contribution are substantive (for example, "thanks to Alice for leading the investment team and delivering strong results").
- Process-driving transition sentences are boilerplate if they only hand off the call or describe the speaking order without naming a specific business topic (for example, "next I'll turn it over to Bob").
- Process-driving transition sentences are substantive if they identify the specific topic being introduced (for example, "next I'll ask Bob to discuss the performance of the cloud division" or "turning now to our capital allocation priorities").
- Sentences that only provide information sources or navigation cues are boilerplate (for example, "the data is on slide 26").
- Very short wrap-up or summary sentences are boilerplate (for example, "that is our work" or "that is the update").

""".strip()
