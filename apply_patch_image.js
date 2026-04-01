const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

const regex = /return \([\s\S]*?<div ref=\{containerRef\} className="contents">[\s\S]*?<img[\s\S]*?src=\{shouldLoad \? resolvedSrc : IMG_PLACEHOLDER_SRC\}[\s\S]*?\{...restImgProps\}[\s\S]*?\/\>[\s\S]*?<\/div>[\s\S]*?\);/;

const replacement = `return (
        <div ref={containerRef} className={\`relative flex items-center justify-center overflow-hidden bg-[#151515] \${className ? className.replace('object-cover', '').replace('object-contain', '') : ''}\`}>
            {!isLoaded && !failed && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-0">
                    <Loader2 className="w-5 h-5 animate-spin text-white/20" />
                </div>
            )}
            <img
                src={shouldLoad ? resolvedSrc : IMG_PLACEHOLDER_SRC}
                alt={alt}
                className={\`absolute inset-0 w-full h-full transition-all duration-700 z-10 \${(className || '').includes('object-contain') ? 'object-contain' : 'object-cover'} \${
                    isLoaded ? 'opacity-100 blur-0 scale-100 bg-transparent' : 'opacity-0 blur-[10px] scale-110 bg-[#151515]'
                }\`}
                loading={imgProps.loading || 'lazy'}
                decoding={imgProps.decoding || 'async'}
                fetchPriority={imgProps.fetchPriority || 'low'}
                onLoad={() => {
                    rememberWarmMediaUrl(rawSrc);
                    setIsLoaded(true);
                    if (typeof userOnLoad === 'function') userOnLoad();
                }}
                onError={() => {
                    if (!shouldLoad) {
                        setShouldLoad(true);
                        if (typeof userOnError === 'function') userOnError();
                        return;
                    }
                    rememberBrokenMediaUrl(rawSrc);
                    setFailed(true);
                    if (typeof userOnError === 'function') userOnError();
                }}
                {...restImgProps}
            />
        </div>
    );`;

if(content.match(regex)) {
    content = content.replace(regex, replacement);
    fs.writeFileSync('frontend/src/pages/Editor.jsx', content, 'utf8');
    console.log("SafeImage replacing success.");
} else {
    console.log("regex not matched");
}
