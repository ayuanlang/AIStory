const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

const oldState = `const [shouldLoad, setShouldLoad] = useState(() => isWarmMediaUrl(src));
    const [videoFailed, setVideoFailed] = useState(() => !src || isBrokenMediaUrl(src));
    const [posterFailed, setPosterFailed] = useState(() => !poster || isBrokenMediaUrl(poster));

    useEffect(() => {
        setVideoFailed(!src || isBrokenMediaUrl(src));
        if (isWarmMediaUrl(src)) {
            setShouldLoad(true);
        }
    }, [src]);`;

const newState = `const [shouldLoad, setShouldLoad] = useState(() => isWarmMediaUrl(src));
    const [videoFailed, setVideoFailed] = useState(() => !src || isBrokenMediaUrl(src));
    const [posterFailed, setPosterFailed] = useState(() => !poster || isBrokenMediaUrl(poster));
    const [isVideoLoaded, setIsVideoLoaded] = useState(() => isWarmMediaUrl(src));

    useEffect(() => {
        setVideoFailed(!src || isBrokenMediaUrl(src));
        if (isWarmMediaUrl(src)) {
            setShouldLoad(true);
            setIsVideoLoaded(true);
        }
    }, [src]);`;

content = content.replace(oldState, newState);

const regexRender = /return \([\s\S]*?<div\s+ref=\{containerRef\}[\s\S]*?className=\{className\}[\s\S]*?onMouseEnter=\{handleMouseEnter\}[\s\S]*?onMouseLeave=\{handleMouseLeave\}\s*>[\s\S]*?<video[\s\S]*?src=\{shouldLoad && !videoFailed \? getFullUrl\(src\) : undefined\}[\s\S]*?\{...videoProps\}[\s\S]*?\/\>[\s\S]*?<\/div>[\s\S]*?\);/;

const replacementRender = `return (
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
        </div>
    );`;

if(content.match(regexRender)) {
    content = content.replace(regexRender, replacementRender);
    fs.writeFileSync('frontend/src/pages/Editor.jsx', content, 'utf8');
    console.log("LazyHoverVideo replacing success.");
} else {
    console.log("regexRender not matched");
}
