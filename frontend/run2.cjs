const fs = require("fs");
let code = fs.readFileSync("src/pages/Settings.jsx", "utf8");

// Change {tUI(' to {t(' and so on
code = code.replace(/\{tUI\('/g, "{t('");
code = code.replace(/\{tUI\("/g, '{t("');
code = code.replace(/ displayName = tUI\('/g, " displayName = t('");
code = code.replace(/ title=\{tUI\('/g, " title={t('");

fs.writeFileSync("src/pages/Settings.jsx", code, "utf8");
console.log("Replaced tUI with t in Settings.jsx");