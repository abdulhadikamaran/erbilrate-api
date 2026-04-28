/**
 * i18n — Kurdish / English translation system
 */
const translations = {
    ku: {
        app_name: "نرخی دۆلار",
        live_market: "بازاڕی ڕاستەوخۆ",
        per_100: "IQD بۆ $100",
        updated_ago: "{n} خولەک لەمەوپێش",
        updated_hr_min: "{h} کاتژمێر و {m} خولەک لەمەوپێش",
        updated_day_hr: "{d} ڕۆژ و {h} کاتژمێر لەمەوپێش",
        updated_just: "ئێستا نوێکراوەتەوە",
        selling: "فرۆشتن",
        buying: "کڕین",
        alerts: "ئاگاداری",
        set_price: "تێبینی نرخ",
        analysis: "شیکاری",
        market_trends: "ڕەوتی بازاڕ",
        home: "سەرەتا",
        history: "مێژوو",
        rates: "نرخەکان",
        convert: "گۆڕین",
        settings: "ڕێکخستن",
        today: "ئەمڕۆ",
        days_1: "١ ڕۆژ",
        days_7: "٧ ڕۆژ",
        days_30: "٣٠ ڕۆژ",
        days_90: "٩٠ ڕۆژ",
        weekly_high: "بەرزترین هەفتانە",
        weekly_low: "نزمترین هەفتانە",
        daily_high: "بەرزترین ئەمڕۆ",
        daily_low: "نزمترین ئەمڕۆ",
        monthly_high: "بەرزترین مانگانە",
        monthly_low: "نزمترین مانگانە",
        period_high: "بەرزترین",
        period_low: "نزمترین",
        trend: "ڕەوت",
        bullish: "بەرزبوونەوە",
        bearish: "دابەزین",
        volume: "قەبارە",
        high: "بەرز",
        low: "نزم",
        offline_banner: "ئۆفلاین — نرخی {time} لەمەوپێش",
        no_data: "هیچ داتایەک نییە",
        market_closed: "بازاڕ داخراوە",
        analytics: "شیکاری",
        iqd_usd_rate: "نرخی IQD/USD",
        iqd: "IQD",
        data_source: "سەرچاوەی داتا: @iraqborsa",
        lang_toggle: "EN",
        mon: "دوو",
        tue: "سێ",
        wed: "چوار",
        thu: "پێنج",
        fri: "هەینی",
        sat: "شەم",
        sun: "یەک",
    },
    en: {
        app_name: "Dollar Rate",
        live_market: "Live Market",
        per_100: "IQD per $100",
        updated_ago: "{n} mins ago",
        updated_hr_min: "{h} hr {m} min ago",
        updated_day_hr: "{d} day {h} hr ago",
        updated_just: "Just updated",
        selling: "Selling",
        buying: "Buying",
        alerts: "Alerts",
        set_price: "Set price triggers",
        analysis: "Analysis",
        market_trends: "Market trends",
        home: "Home",
        history: "History",
        rates: "Rates",
        convert: "Convert",
        settings: "Settings",
        today: "Today",
        days_1: "1D",
        days_7: "7D",
        days_30: "30D",
        days_90: "90D",
        weekly_high: "Weekly High",
        weekly_low: "Weekly Low",
        daily_high: "Daily High",
        daily_low: "Daily Low",
        monthly_high: "Monthly High",
        monthly_low: "Monthly Low",
        period_high: "High",
        period_low: "Low",
        trend: "Trend",
        bullish: "Bullish",
        bearish: "Bearish",
        volume: "Vol.",
        high: "High",
        low: "Low",
        offline_banner: "Offline — rate from {time} ago",
        no_data: "No data available",
        market_closed: "Market Closed",
        analytics: "Analytics",
        iqd_usd_rate: "IQD/USD Rate",
        iqd: "IQD",
        data_source: "Data from @iraqborsa",
        lang_toggle: "کو",
        mon: "Mon",
        tue: "Tue",
        wed: "Wed",
        thu: "Thu",
        fri: "Fri",
        sat: "Sat",
        sun: "Sun",
    },
};

let currentLang = localStorage.getItem("lang") || "ku";

export function t(key) {
    return translations[currentLang]?.[key] || translations.en[key] || key;
}

export function getLang() {
    return currentLang;
}

export function setLang(lang) {
    currentLang = lang;
    localStorage.setItem("lang", lang);
    // Update document direction
    document.documentElement.dir = lang === "ku" ? "rtl" : "ltr";
    document.documentElement.lang = lang;
}

export function toggleLang() {
    const next = currentLang === "ku" ? "en" : "ku";
    setLang(next);
    return next;
}
