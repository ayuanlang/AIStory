const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

// Patch SafeImage
const safeImageRegex = /const SafeImage[\s\S]*?return \(\s*<div ref=\{containerRef\} className="contents">\s*<img[\s\S]*?\{...restImgProps\}\s*\/>\s*<\/div>\s*\);\s*\};/m;

const safeImageMatch = content.match(safeImageRegex);
if (safeImageMatch) {
    let replaced = safeImageMatch[0].replace(
        /<div ref=\{containerRef\} className="contents">\s*<img[\s\S]*?\{...restImgProps\}\s*\/>\s*<\/div>/,
        `<div ref={containerRef} className={\`relative flex items-center justify-center overflow-hidden bg-[#151515] \${className ? className.replace('object-cover', '').replace('object-contain', '') : ''}\`}>
            {!isLoaded && !failed && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-0">
                    <Loader2 className="w-5 h-5 animate-spin text-white/20" />
                </div>
            )}
            <img
                src={shouldLoad ? resolvedSrc : 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='}
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
        </div>`
    );
    content = content.replace(safeImageMatch[0], replaced);
    console.log("SafeImage patched");
} else {
    console.log("SafeImage NOT found");
}

// Patch LazyHoverVideo
const lazyHoverRegex = /const LazyHoverVideo[\s\S]*?const \[posterFailed, setPosterFailed\] = useState\(\(\) => !poster \|\| isBrokenMediaUrl\(poster\)\);[\s\S]*?useEffect\(\(\) => \{[\s\S]*?setShouldLoad\(true\);[\s\S]*?\}, \[src\]\);[\s\S]*?return \([\s\S]*?\{...videoProps\}\s*\/>\s*<\/div>\s*\);\s*\};/m;

const lazyMatch = content.match(lazyHoverRegex);
if (lazyMatch) {
    let replaced = lazyMatch[0].replace(
        /const \[posterFailed, setPosterFailed\] = useState\(\(\) => !poster \|\| isBrokenMediaUrl\(poster\)\);/,
        `const [posterFailed, setPosterFailed] = useState(() => !poster || isBrokenMediaUrl(poster));\n    const [isVideoLoaded, setIsVideoLoaded] = useState(() => isWarmMediaUrl(src));`
    );
    replaced = replaced.replace(
        /setShouldLoad\(true\);/g,
        `setShouldLoad(true);\n            setIsVideoLoaded(true);`
    );
    replaced = replaced.replace(
        /<div\s+ref=\{containerRef\}\s+className=\{className\}\s+onMouseEnter=\{handleMouseEnter\}\s+onMouseLeave=\{handleMouseLeave\}\s*>[\s\S]*?<\/div>/,
        `<div
            ref={containerRef}
            className={\`relative flex items-center justify-center overflow-hidden bg-[#151515] \${className ? className.replace('relative', '') : ''}\`}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            {!isVideoLoaded && !videoFailed && !poster && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-0">
                    <Loader2 className="w-5 h-5 animate-spin text-white/20" />
                </div>
            )}
            
            {!posterFailed && poster && (
                <div className={\`absolute inset-0 z-0 transition-opacity duration-700 \${isVideoLoaded ? 'opacity-0 delay-300' : 'opacity-100'}\`}>
                    <SafeImage src={poster} className="absolute inset-0 w-full h-full object-cover" />
                </div>
            )}

            <video
                ref={videoRef}
                src={shouldLoad && !videoFailed ? getFullUrl(src) : undefined}
                preload={shouldLoad ? preload : 'none'}
                className={\`z-10 relative transition-all duration-700 \${mediaClassName} \${isVideoLoaded ? 'opacity-100 blur-0 scale-100 bg-transparent' : 'opacity-0 blur-[10px] scale-105 bg-[#151515]'}\`}
                onLoadedData={() => {
                    setIsVideoLoaded(true);
                    rememberWarmMediaUrl(src);
                    if (poster) rememberWarmMediaUrl(poster);
                }}
                onError={() => {
                    if (src) rememberBrokenMediaUrl(src);
                    setVideoFailed(true);
                    if (poster) {
                        rememberBrokenMediaUrl(poster);
                        setPosterFailed(true);
                    }
                }}
                {...videoProps}
            />
        </div>`
    );
    content = content.replace(lazyMatch[0], replaced);
    console.log("LazyHoverVideo patched");
} else {
    console.log("LazyHoverVideo NOT found");
}

fs.writeFileSync('frontend/src/pages/Editor.jsx', content, 'utf8');

