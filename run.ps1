
$file = "frontend\src\pages\editor\components\ScriptEditor.jsx"
$content = Get-Content $file -Raw -Encoding UTF8

$find = @`
{isRawMode && (
                          <>
                              <button
                                  onClick={handleAnalysisClick} 
                                  disabled={isAnalyzing}
`@

$replace = @`
{isRawMode && (
                          <div className="flex items-center gap-2">
                              <FunctionApiSelector functionName="script_analysis" configs={functionApiConfigs} />
                              <button
                                  onClick={handleAnalysisClick} 
                                  disabled={isAnalyzing}
`@

$content = $content.Replace($find, $replace)

# we also need to close the div instead of </>
$find2 = @`
                                      </>
                                  )}
                              </button>
`@

$replace2 = @`
                                      </>
                                  )}
                              </button>
                          </div>
`@

$content = $content.Replace($find2, $replace2)

Set-Content $file $content -Encoding UTF8

