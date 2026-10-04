import type { Lang, Step, Verdict } from "./types";

// UI strings. Bengali and Hindi need native-speaker review before the demo.
const S = {
  appTagline: {
    en: "Understand your loan or rent paper before you sign",
    bn: "সই করার আগে আপনার ঋণ বা ভাড়ার কাগজ বুঝে নিন",
    hi: "दस्तख़त से पहले अपना कर्ज़ या किराए का कागज़ समझें",
  },
  offlineBadge: { en: "Works offline", bn: "ইন্টারনেট ছাড়াই চলে", hi: "बिना इंटरनेट चलता है" },
  notAdvice: {
    en: "This is help to understand, not legal advice. For big decisions, talk to a lawyer or call the consumer helpline 1915.",
    bn: "এটা বোঝার সাহায্য, আইনি পরামর্শ নয়। বড় সিদ্ধান্তের আগে আইনজীবীর সঙ্গে কথা বলুন বা ক্রেতা হেল্পলাইন 1915-এ ফোন করুন।",
    hi: "यह समझने में मदद है, कानूनी सलाह नहीं। बड़े फ़ैसलों से पहले वकील से बात करें या उपभोक्ता हेल्पलाइन 1915 पर फ़ोन करें।",
  },
  takePhoto: { en: "Take a photo", bn: "ছবি তুলুন", hi: "फ़ोटो लें" },
  uploadPhoto: { en: "Choose a photo", bn: "ছবি বেছে নিন", hi: "फ़ोटो चुनें" },
  pasteText: { en: "Type or paste the text", bn: "লেখা টাইপ বা পেস্ট করুন", hi: "लिखा हुआ टाइप या पेस्ट करें" },
  capture: { en: "Capture", bn: "তুলুন", hi: "खींचें" },
  trySample: {
    en: "Or try a sample contract (made-up data):",
    bn: "অথবা একটি নমুনা চুক্তি দেখুন (কাল্পনিক তথ্য):",
    hi: "या एक नमूना समझौता आज़माएं (काल्पनिक जानकारी):",
  },
  cancel: { en: "Cancel", bn: "বাতিল", hi: "रद्द करें" },
  reading: { en: "Reading your paper…", bn: "আপনার কাগজ পড়া হচ্ছে…", hi: "आपका कागज़ पढ़ा जा रहा है…" },
  retakeTitle: { en: "The photo may be hard to read", bn: "ছবিটা পড়তে অসুবিধা হতে পারে", hi: "फ़ोटो पढ़ने में मुश्किल हो सकती है" },
  blurry: { en: "It looks blurry. Hold the phone still.", bn: "ছবিটা ঝাপসা। ফোন স্থির রাখুন।", hi: "फ़ोटो धुंधली है। फ़ोन स्थिर रखें।" },
  too_dark: { en: "It is too dark. Move to better light.", bn: "খুব অন্ধকার। আলোয় নিয়ে যান।", hi: "बहुत अंधेरा है। रोशनी में ले जाएं।" },
  too_bright: { en: "It is too bright or has glare.", bn: "খুব উজ্জ্বল বা চকচক করছে।", hi: "बहुत चमक है।" },
  too_small: { en: "The photo is too small. Come closer.", bn: "ছবি খুব ছোট। কাছে আসুন।", hi: "फ़ोटो बहुत छोटी है। पास आएं।" },
  retake: { en: "Take again", bn: "আবার তুলুন", hi: "फिर से लें" },
  continueAnyway: { en: "Continue anyway", bn: "তবুও এগিয়ে যান", hi: "फिर भी आगे बढ़ें" },
  checkTitle: { en: "Is this what your paper says?", bn: "আপনার কাগজে কি এটাই লেখা?", hi: "क्या आपके कागज़ पर यही लिखा है?" },
  checkHelp: {
    en: "Fix any wrong words. Lines in yellow were hard to read.",
    bn: "ভুল শব্দ ঠিক করুন। হলুদ লাইনগুলো পড়তে কষ্ট হয়েছে।",
    hi: "गलत शब्द ठीक करें। पीली लाइनें पढ़ने में मुश्किल थीं।",
  },
  hiddenInfo: { en: "Hidden for your privacy", bn: "আপনার গোপনীয়তার জন্য লুকানো", hi: "आपकी गोपनीयता के लिए छिपाया गया" },
  aadhaar: { en: "Aadhaar", bn: "আধার", hi: "आधार" },
  phone: { en: "phone", bn: "ফোন", hi: "फ़ोन" },
  pan: { en: "PAN", bn: "PAN", hi: "PAN" },
  email: { en: "email", bn: "ইমেল", hi: "ईमेल" },
  showOriginal: { en: "Show original", bn: "আসল ছবি দেখুন", hi: "असली फ़ोटो देखें" },
  showHidden: { en: "Show with hiding", bn: "লুকানো সহ দেখুন", hi: "छिपाकर देखें" },
  lowConfWarn: {
    en: "Some parts were hard to read. Please check them.",
    bn: "কিছু অংশ পড়তে কষ্ট হয়েছে। দয়া করে মিলিয়ে নিন।",
    hi: "कुछ हिस्से पढ़ने में मुश्किल थे। कृपया जांच लें।",
  },
  checkMyPaper: { en: "Check my paper", bn: "আমার কাগজ পরীক্ষা করুন", hi: "मेरा कागज़ जांचें" },
  progressAnalyze: { en: "Reading part {i} of {n}…", bn: "{n}টির মধ্যে {i} নম্বর অংশ পড়া হচ্ছে…", hi: "{n} में से {i} हिस्सा पढ़ा जा रहा है…" },
  progressTerms: { en: "Finding the money terms…", bn: "টাকার হিসাব খোঁজা হচ্ছে…", hi: "पैसों की शर्तें ढूंढी जा रही हैं…" },
  progressRules: { en: "Checking against the rule list…", bn: "নিয়মের তালিকার সঙ্গে মেলানো হচ্ছে…", hi: "नियमों की सूची से मिलाया जा रहा है…" },
  progressLocalize: { en: "Writing explanation {i} of {n}…", bn: "{n}টির মধ্যে {i} নম্বর ব্যাখ্যা লেখা হচ্ছে…", hi: "{n} में से {i} व्याख्या लिखी जा रही है…" },
  fallbackEngine: {
    en: "The AI model is not running, so this uses a simple keyword check. Results are less detailed.",
    bn: "AI মডেল চলছে না, তাই সাধারণ শব্দ-মিলিয়ে দেখা হয়েছে। ফল কম বিস্তারিত।",
    hi: "AI मॉडल नहीं चल रहा, इसलिए साधारण शब्द-जांच की गई है। नतीजे कम विस्तृत हैं।",
  },
  moneyTitle: { en: "The money", bn: "টাকার হিসাব", hi: "पैसों का हिसाब" },
  youGet: { en: "You get in hand", bn: "আপনার হাতে আসবে", hi: "आपके हाथ में आएंगे" },
  youPay: { en: "You pay back", bn: "আপনি ফেরত দেবেন", hi: "आप लौटाएंगे" },
  extra: { en: "Extra you pay", bn: "বাড়তি দিচ্ছেন", hi: "ज़्यादा दे रहे हैं" },
  aprLine: { en: "Real yearly cost (APR)", bn: "বছরে আসল খরচ (APR)", hi: "साल का असली खर्च (APR)" },
  paperSays: { en: "Paper says", bn: "কাগজে লেখা", hi: "कागज़ पर लिखा" },
  perYear: { en: "per year", bn: "বছরে", hi: "सालाना" },
  showSteps: { en: "Show the calculation", bn: "হিসাবটা দেখুন", hi: "हिसाब देखें" },
  verifiedByCode: {
    en: "Calculated by the app's code, not by the AI.",
    bn: "এই হিসাব অ্যাপের কোড করেছে, AI নয়।",
    hi: "यह हिसाब ऐप के कोड ने किया है, AI ने नहीं।",
  },
  fixNumbers: { en: "Numbers wrong? Fix them", bn: "সংখ্যা ভুল? ঠিক করুন", hi: "संख्या गलत? ठीक करें" },
  recalc: { en: "Recalculate", bn: "আবার হিসাব করুন", hi: "फिर से हिसाब करें" },
  moneyMissing: {
    en: "Could not find all the loan numbers. Enter them below to see the real cost.",
    bn: "ঋণের সব সংখ্যা পাওয়া যায়নি। আসল খরচ দেখতে নিচে লিখুন।",
    hi: "कर्ज़ की सारी संख्याएं नहीं मिलीं। असली खर्च देखने के लिए नीचे भरें।",
  },
  threeThings: { en: "3 things to ask before signing", bn: "সই করার আগে ৩টি প্রশ্ন করুন", hi: "दस्तख़त से पहले 3 सवाल पूछें" },
  playAll: { en: "Play all", bn: "সব শুনুন", hi: "सब सुनें" },
  listen: { en: "Listen", bn: "শুনুন", hi: "सुनें" },
  stop: { en: "Stop", bn: "থামুন", hi: "रोकें" },
  noVoice: {
    en: "No offline voice installed for this language.",
    bn: "এই ভাষার অফলাইন কণ্ঠ ইনস্টল করা নেই।",
    hi: "इस भाषा की ऑफ़लाइन आवाज़ इंस्टॉल नहीं है।",
  },
  tapClause: { en: "Tap a coloured part of the paper", bn: "কাগজের রঙিন অংশে চাপ দিন", hi: "कागज़ के रंगीन हिस्से पर दबाएं" },
  clause: { en: "Part", bn: "অংশ", hi: "हिस्सा" },
  whatItSays: { en: "What it says", bn: "কী বলছে", hi: "क्या कहता है" },
  whyItMatters: { en: "Why it matters", bn: "কেন জরুরি", hi: "क्यों ज़रूरी है" },
  questionsToAsk: { en: "Questions to ask", bn: "যা জিজ্ঞেস করবেন", hi: "क्या पूछें" },
  askToChange: { en: "Change to ask for", bn: "যে পরিবর্তন চাইবেন", hi: "क्या बदलवाएं" },
  compare: { en: "Paper vs fairer version", bn: "কাগজের লেখা বনাম ন্যায্য লেখা", hi: "कागज़ बनाम उचित लेख" },
  onPaper: { en: "On your paper", bn: "আপনার কাগজে", hi: "आपके कागज़ पर" },
  fairer: { en: "Fairer version (AI suggestion)", bn: "ন্যায্য লেখা (AI-এর প্রস্তাব)", hi: "उचित लेख (AI सुझाव)" },
  lawRefs: { en: "Rules and laws (from our checked list)", bn: "নিয়ম ও আইন (আমাদের যাচাই করা তালিকা থেকে)", hi: "नियम और कानून (हमारी जांची गई सूची से)" },
  unverified: { en: "not yet verified by our team", bn: "আমাদের দল এখনও যাচাই করেনি", hi: "हमारी टीम ने अभी जांचा नहीं" },
  verifiedOn: { en: "verified", bn: "যাচাই", hi: "जांचा" },
  reasoning: {
    en: "How the AI reasoned (model output, not checked)",
    bn: "AI কীভাবে ভেবেছে (মডেলের লেখা, যাচাই করা নয়)",
    hi: "AI ने कैसे सोचा (मॉडल का लिखा, जांचा नहीं गया)",
  },
  raisedByRules: {
    en: "Marked more serious by a fixed rule check.",
    bn: "নির্দিষ্ট নিয়ম-পরীক্ষায় বেশি গুরুতর ধরা হয়েছে।",
    hi: "तय नियम-जांच ने इसे ज़्यादा गंभीर माना।",
  },
  lowConfCard: {
    en: "This part was hard to read. The text may have mistakes.",
    bn: "এই অংশ পড়তে কষ্ট হয়েছে। লেখায় ভুল থাকতে পারে।",
    hi: "यह हिस्सा पढ़ने में मुश्किल था। लेख में गलती हो सकती है।",
  },
  notChecked: {
    en: "Not checked in detail (no risk words found).",
    bn: "বিস্তারিত পরীক্ষা করা হয়নি (ঝুঁকির শব্দ পাওয়া যায়নি)।",
    hi: "विस्तार से नहीं जांचा गया (जोखिम वाले शब्द नहीं मिले)।",
  },
  checkingPart: { en: "Checking this part…", bn: "এই অংশটি দেখা হচ্ছে…", hi: "यह हिस्सा जांचा जा रहा है…" },
  askTitle: { en: "Ask about this paper", bn: "এই কাগজ নিয়ে প্রশ্ন করুন", hi: "इस कागज़ के बारे में पूछें" },
  askPlaceholder: { en: "e.g. What happens if I pay late?", bn: "যেমন: দেরিতে দিলে কী হবে?", hi: "जैसे: देर से देने पर क्या होगा?" },
  ask: { en: "Ask", bn: "জিজ্ঞেস করুন", hi: "पूछें" },
  speakQuestion: { en: "Ask by voice", bn: "বলে জিজ্ঞেস করুন", hi: "बोलकर पूछें" },
  stopRecording: { en: "Stop", bn: "থামান", hi: "रोकें" },
  listening: {
    en: "Listening… speak in Bengali, Hindi or English ({s} s)",
    bn: "শুনছি… বাংলা, হিন্দি বা ইংরেজিতে বলুন ({s} সে.)",
    hi: "सुन रहे हैं… बांग्ला, हिंदी या अंग्रेज़ी में बोलें ({s} से.)",
  },
  hearing: { en: "Understanding your question…", bn: "আপনার প্রশ্ন বোঝা হচ্ছে…", hi: "आपका सवाल समझा जा रहा है…" },
  answering: { en: "Finding the answer in the paper…", bn: "কাগজে উত্তর খোঁজা হচ্ছে…", hi: "कागज़ में जवाब ढूंढा जा रहा है…" },
  notHeard: {
    en: "Could not hear a question. Please try again, or type it.",
    bn: "প্রশ্নটি শোনা যায়নি। আবার বলুন, বা লিখে দিন।",
    hi: "सवाल सुनाई नहीं दिया। फिर से बोलें, या लिखें।",
  },
  micDenied: {
    en: "The microphone is blocked. Allow it in the browser, or type the question.",
    bn: "মাইক্রোফোন বন্ধ আছে। ব্রাউজারে অনুমতি দিন, বা প্রশ্ন লিখে দিন।",
    hi: "माइक्रोफ़ोन बंद है। ब्राउज़र में अनुमति दें, या सवाल लिखें।",
  },
  voiceNeedsGemma: {
    en: "Voice questions need Gemma to be running. Please type the question.",
    bn: "বলে প্রশ্ন করতে Gemma চালু থাকা দরকার। প্রশ্নটি লিখে দিন।",
    hi: "बोलकर पूछने के लिए Gemma चालू होना चाहिए। सवाल लिखें।",
  },
  fromPart: { en: "From part", bn: "অংশ থেকে", hi: "हिस्से से" },
  makeLetter: { en: "Letter asking for changes", bn: "পরিবর্তন চেয়ে চিঠি", hi: "बदलाव मांगने का पत्र" },
  back: { en: "Back", bn: "ফিরে যান", hi: "वापस" },
  copy: { en: "Copy", bn: "কপি", hi: "कॉपी" },
  copied: { en: "Copied", bn: "কপি হয়েছে", hi: "कॉपी हो गया" },
  print: { en: "Print / Save PDF", bn: "প্রিন্ট / PDF", hi: "प्रिंट / PDF" },
  letterExplain: { en: "What this letter asks for", bn: "এই চিঠিতে কী চাওয়া হচ্ছে", hi: "यह पत्र क्या मांगता है" },
  wipe: { en: "Wipe everything", bn: "সব মুছে ফেলুন", hi: "सब मिटाएं" },
  wiped: { en: "Everything was deleted from this computer.", bn: "এই কম্পিউটার থেকে সব মুছে ফেলা হয়েছে।", hi: "इस कंप्यूटर से सब मिटा दिया गया।" },
  bigText: { en: "Big text", bn: "বড় লেখা", hi: "बड़ा लेख" },
  selfcheck: { en: "Offline check", bn: "অফলাইন পরীক্ষা", hi: "ऑफ़लाइन जांच" },
  help: { en: "Where to get help", bn: "কোথায় সাহায্য পাবেন", hi: "मदद कहां मिलेगी" },
  docWide: { en: "About the whole paper", bn: "পুরো কাগজ নিয়ে", hi: "पूरे कागज़ के बारे में" },
  startOver: { en: "New paper", bn: "নতুন কাগজ", hi: "नया कागज़" },
  error: { en: "Something went wrong", bn: "কিছু একটা ভুল হয়েছে", hi: "कुछ गड़बड़ हुई" },
  timeTaken: { en: "Time taken", bn: "সময় লেগেছে", hi: "समय लगा" },
} as const;

export type Key = keyof typeof S;

export function t(lang: Lang, key: Key, vars?: Record<string, string | number>): string {
  let s: string = S[key][lang] ?? S[key].en;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
}

export const VERDICT_LABEL: Record<Verdict, Record<Lang, string>> = {
  NOT_OK: { en: "Not OK", bn: "ঠিক নয়", hi: "ठीक नहीं" },
  CAREFUL: { en: "Be careful", bn: "সাবধান", hi: "सावधान" },
  OK: { en: "Looks OK", bn: "ঠিক আছে", hi: "ठीक है" },
  UNCHECKED: { en: "Not checked", bn: "দেখা হয়নি", hi: "जांचा नहीं" },
};

export const LANG_NAMES: Record<Lang, string> = { bn: "বাংলা", hi: "हिन्दी", en: "English" };
export const SPEECH_LANG: Record<Lang, string> = { bn: "bn-IN", hi: "hi-IN", en: "en-IN" };

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
export const rupees = (x: number) => `₹${Math.abs(x - Math.round(x)) > 0.004 ? inr2.format(x) : inr.format(x)}`;
export const pct = (x: number, d = 1) => `${x.toFixed(d)}%`;

const UNIT: Record<string, Record<Lang, string>> = {
  day: { en: "day", bn: "দিন", hi: "दिन" },
  week: { en: "week", bn: "সপ্তাহ", hi: "हफ्ता" },
  fortnight: { en: "fortnight", bn: "পাক্ষিক", hi: "पखवाड़ा" },
  month: { en: "month", bn: "মাস", hi: "महीना" },
  quarter: { en: "quarter", bn: "ত্রৈমাসিক", hi: "तिमाही" },
  year: { en: "year", bn: "বছর", hi: "साल" },
};
const unit = (u: string | number, lang: Lang) => UNIT[String(u)]?.[lang] ?? String(u);

/** Localised rendering of the calculator's steps (numbers come from the backend). */
export function stepText(s: Step, lang: Lang): string {
  const v = s.values as Record<string, any>;
  const R = rupees;
  const L: Record<string, Record<Lang, () => string>> = {
    cash_in_hand: {
      en: () => `Loan ${R(v.principal)} − fees taken at start ${R(v.fees)} = ${R(v.cash)} in your hand`,
      bn: () => `ঋণ ${R(v.principal)} − শুরুতেই কাটা ফি ${R(v.fees)} = হাতে আসবে ${R(v.cash)}`,
      hi: () => `कर्ज़ ${R(v.principal)} − शुरू में कटी फीस ${R(v.fees)} = हाथ में ${R(v.cash)}`,
    },
    cash_in_hand_nofee: {
      en: () => `You receive ${R(v.cash)}`,
      bn: () => `আপনি পাবেন ${R(v.cash)}`,
      hi: () => `आपको मिलेंगे ${R(v.cash)}`,
    },
    installment_from_rate: {
      en: () => `Paper says ${v.rate}% per ${unit(v.period, lang)} (${v.rate_type}), so each payment is ${R(v.installment)}`,
      bn: () => `কাগজে ${v.rate}% প্রতি ${unit(v.period, lang)} (${v.rate_type}), তাই প্রতি কিস্তি ${R(v.installment)}`,
      hi: () => `कागज़ पर ${v.rate}% प्रति ${unit(v.period, lang)} (${v.rate_type}), इसलिए हर किस्त ${R(v.installment)}`,
    },
    installments: {
      en: () => `${v.n} payments (one per ${unit(v.unit, lang)}) × ${R(v.installment)} = ${R(v.subtotal)}`,
      bn: () => `${v.n}টি কিস্তি (প্রতি ${unit(v.unit, lang)}) × ${R(v.installment)} = ${R(v.subtotal)}`,
      hi: () => `${v.n} किस्तें (हर ${unit(v.unit, lang)}) × ${R(v.installment)} = ${R(v.subtotal)}`,
    },
    balloon: {
      en: () => `Plus a last lump sum of ${R(v.balloon)}`,
      bn: () => `সঙ্গে শেষে একবারে ${R(v.balloon)}`,
      hi: () => `साथ में आख़िर में एकमुश्त ${R(v.balloon)}`,
    },
    total_repayment: {
      en: () => `Total you pay back: ${R(v.total)}`,
      bn: () => `মোট ফেরত দেবেন: ${R(v.total)}`,
      hi: () => `कुल लौटाएंगे: ${R(v.total)}`,
    },
    extra_cost: {
      en: () => `${R(v.total)} − ${R(v.cash)} = ${R(v.extra)} extra`,
      bn: () => `${R(v.total)} − ${R(v.cash)} = ${R(v.extra)} বাড়তি`,
      hi: () => `${R(v.total)} − ${R(v.cash)} = ${R(v.extra)} ज़्यादा`,
    },
    periodic_rate: {
      en: () => `The rate per ${unit(v.unit, lang)} that turns ${R(v.cash ?? 0)} into these payments is ${pct(v.rate, 3)}`,
      bn: () => `প্রতি ${unit(v.unit, lang)} আসল সুদের হার ${pct(v.rate, 3)}`,
      hi: () => `हर ${unit(v.unit, lang)} की असली ब्याज दर ${pct(v.rate, 3)}`,
    },
    apr: {
      en: () => `${pct(v.periodic, 3)} × ${v.ppy} ${unit(v.unit, lang)}s in a year = ${pct(v.apr)} per year (APR)`,
      bn: () => `${pct(v.periodic, 3)} × বছরে ${v.ppy} ${unit(v.unit, lang)} = বছরে ${pct(v.apr)} (APR)`,
      hi: () => `${pct(v.periodic, 3)} × साल में ${v.ppy} ${unit(v.unit, lang)} = सालाना ${pct(v.apr)} (APR)`,
    },
    stated: {
      en: () => `The paper says ${v.rate}% per ${unit(v.period, lang)} = ${pct(v.annual)} per year`,
      bn: () => `কাগজে লেখা ${v.rate}% প্রতি ${unit(v.period, lang)} = বছরে ${pct(v.annual)}`,
      hi: () => `कागज़ पर लिखा ${v.rate}% प्रति ${unit(v.period, lang)} = सालाना ${pct(v.annual)}`,
    },
  };
  return L[s.key]?.[lang]() ?? s.text;
}
