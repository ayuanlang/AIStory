const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

const safeImageOld = `    return (
        <div ref={containerRef} className="contents">
            <img
                src={shouldLoad ? resolvedSrc : IMG_PLACEHOLDER_SRC}
                alt={alt}
                className={\`\${className} transition-all duration-300 \${isLoaded ? 'opacity-100 blur-0 scale-100' : 'opacity-85 blur-[3px] scale-[1.01] bg-white/10 animate-pulse'}\`.trim()}
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

const safeImageNew = `    return (
        <div ref={containerRef} className={\`relative flex items-center justify-center overflow-hidden bg-[#151515] \${className ? className.replace('object-cover', '').replace('object-contain', '') : ''}\`}>
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
        </div>
    );`;

if(content.includes(safeImageOld)) {
    content = content.replace(safeImageOld, safeImageNew);
    console.log("SafeImage replaced.");
} else {
    console.log("SafeImage string not found");
}

const lazyHoverStateOld = `const [shouldLoad, setShouldLoad] = useState(() => isWarmMediaUrl(src));
    const [videoFailed, setVideoFailed] = useState(() => !src || isBrokenMediaUrl(src));
    const [posterFailed, setPosterFailed] = useState(() => !poster || isBrokenMediaUrl(poster));`;

const lazyHoverStateNew = `const [shouldLoad, setShouldLoad] = useState(() => isWarmMediaUrl(src));
    const [videoFailed, setVideoFailed] = useState(() => !src || isBrokenMediaUrl(src));
    const [posterFailed, setPosterFailed] = useState(() => !poster || isBrokenMediaUrl(poster));
    const [isVideoLoaded, setIsVideoLoaded] = useState(() => isWarmMediaUrl(src));`;

content = content.replace(lazyHoverStateOld, lazyHoverStateNew);

const lazyHoverEffOld = `if (isWarmMediaUrl(src)) {
            setShouldLoad(true);
        }`;
const lazyHoverEffNew = `if (isWarmMediaUrl(src)) {
            setShouldLoad(true);
            setIsVideoLoaded(true);
        }`;
content = content.replace(lazyHoverEffOld, lazyHoverEffNew);

const lazyHoverRenderOld = `    return (
        <div
            ref={containerRef}
            className={className}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            <video
                ref={videoRef}
                src={shouldLoad && !videoFailed ? getFullUrl(src) : undefined}
                poster={!posterFailed && poster ? getFullUrl(poster) : undefined}
                preload={shouldLoad ? preload : 'none'}
                className={mediaClassName}
                onLoadedData={() => {
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
        </div>
    );`;

const lazyHoverRenderNew = `    return (
        <div
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
                <div className={\`absolute inset-0 z-0 transition-opacity duration-700 \${isVideoLoaded ? 'opacity-0' : 'opacity-100'}\`}>
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
        </div>
    );`;

if(content.includes(lazyHoverRenderOld)) {
    content = content.replace(lazyHoverRenderOld, lazyHoverRenderNew);
    console.log("LazyHoverVideo replaced.");
} else {
    console.log("WAIT, lazyHoverRenderOld not found in file!");
}

fs.writeFileSync('frontend/src/pages/Editor.jsx', content, 'utf8');
console.log("Editor.jsx successfully patched");

