
import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Sparkles, Play } from 'lucide-react';
import Navbar from '../components/Navbar';
import { motion } from 'framer-motion';

const Home = () => {
    return (
        <div className="min-h-screen flex flex-col font-sans bg-background text-foreground overflow-hidden selection:bg-primary/20">
            <Navbar />

            {/* Background Effects */}
            <div className="fixed inset-0 z-0 pointer-events-none">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-primary/20 rounded-[100%] blur-[100px] opacity-20" />
                <div className="absolute bottom-0 right-0 w-[800px] h-[600px] bg-purple-500/10 rounded-[100%] blur-[120px] opacity-20" />
                <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]"></div>
            </div>

            {/* Single Hero Page */}
            <main className="flex-grow flex items-center justify-center relative z-10 px-4">
                <div className="container mx-auto max-w-6xl text-center">
                    <motion.div 
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6 }}
                        className="space-y-8"
                    >
                        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/5 border border-primary/20 text-primary text-sm font-medium hover:bg-primary/10 transition-colors cursor-default">
                            <Sparkles className="w-4 h-4" />
                            <span>AI-Powered Storyboard Generation v2.0</span>
                        </div>
                        
                        <h1 className="text-5xl md:text-7xl lg:text-8xl font-black tracking-tight leading-tight">
                            Script to Screen <br />
                            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-primary to-purple-400 animate-gradient">
                                in Minutes
                            </span>
                        </h1>
                        
                        <p className="text-lg md:text-2xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
                            Stop drawing by hand. AI Story transforms your screenplay into 
                            professional, cinematic shots automatically.
                        </p>
                        
                        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-8">
                            <Link to="/auth">
                                <button className="h-14 px-8 rounded-full bg-primary text-primary-foreground text-lg font-bold hover:bg-white/90 transition-all shadow-[0_0_20px_rgba(255,255,255,0.3)] hover:shadow-[0_0_30px_rgba(255,255,255,0.5)] flex items-center gap-2 group">
                                    Start Creating <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform"/>
                                </button>
                            </Link>
                            <button className="h-14 px-8 rounded-full bg-secondary/50 backdrop-blur-sm border border-border text-foreground text-lg font-semibold hover:bg-secondary/80 transition-colors flex items-center gap-2">
                                <Play className="w-5 h-5 fill-current"/> Watch Demo
                            </button>
                        </div>
                    </motion.div>
                </div>
            </main>
            
            <footer className="relative z-10 py-6 text-center text-sm text-muted-foreground">
                <p>&copy; 2024 AI Story. All rights reserved.</p>
            </footer>
        </div>
    );
};

export default Home;
