
const fs = require("fs");
let code = fs.readFileSync("frontend/src/pages/ProjectList.jsx", "utf8");

// Add import
const importSelector = "import FunctionApiSelector, { useFunctionApis } from `../components/FunctionApiSelector`;\n";
code = code.replace(/import \{ Link, useNavigate \} from `"react-router-dom`";/, importSelector + `$&`);

// call hook
code = code.replace(/export default function ProjectList\(\) \{/, `$&
    const functionApiConfigs = useFunctionApis();`);

// inject Component
const targetBtn = `<button
                                    onClick={(e) => handleGenerateProjectCover(e, p)}`;

const newBtn = `<FunctionApiSelector functionName="generate_cover" configs={functionApiConfigs} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                                <button
                                    onClick={(e) => handleGenerateProjectCover(e, p)}`;

code = code.replace(targetBtn, newBtn);
fs.writeFileSync("frontend/src/pages/ProjectList.jsx", code, "utf8");

