import re

with open(r'c:\AS\AIStory\frontend\src\pages\Settings.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

find_blk = """                                                                <Coins className="w-3 h-3" /> {t('充值', 'Top-up')}
                                                            </button>
                                                        </div>
                                                 
                                              </td>"""

repl_blk = """                                                                <Coins className="w-3 h-3" /> {t('充值', 'Top-up')}
                                                            </button>
                                                        </div>
                                                    )}
                                              </td>"""

if find_blk in text:
    text = text.replace(find_blk, repl_blk)
    with open(r'c:\AS\AIStory\frontend\src\pages\Settings.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Fixed missing )}")
else:
    # Attempt a more relaxed regex replace due to spaces/whitespace diffs
    text = re.sub(
        r'</button>\s*</div>\s*(?:<!--.*?-->\s*)?</td>',
        r'</button>\n                                                        </div>\n                                                    )}\n                                              </td>',
        text
    )
    with open(r'c:\AS\AIStory\frontend\src\pages\Settings.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Used regex fix for missing )}")