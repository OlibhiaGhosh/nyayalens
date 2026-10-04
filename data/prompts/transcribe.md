The audio is one spoken question from a person in India about a loan or rental agreement they are reading. They most likely speak {{language}}, but they may use Bengali, Hindi or English, and may mix English words (loan, EMI, interest, deposit) into Bengali or Hindi.

Return JSON only, matching the schema.
- transcript: exactly what was said, in the script of the language spoken (Bengali in Bengali script, Hindi in Devanagari, English in Latin). Do not translate, answer, correct or add anything. Write numbers as digits.
- language: "bn", "hi" or "en" for the main language spoken; "other" if it is none of these.
- If there is no clear speech, return an empty transcript.
