
import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Clapperboard, Menu, X } from 'lucide-react';
import { motion } from 'framer-motion';

const Navbar = () => {
    const [scrolled, setScrolled] = useState(false);
    const [isOpen, setIsOpen] = useState(false);
    const navigate = useNavigate();
    const isLoggedIn = !!localStorage.getItem('token');

    useEffect(() => {
        const handleScroll = () => setScrolled(window.scrollY > 20);
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    const handleLogout = () => {
        localStorage.removeItem('token');
        navigate('/');
    };

    return (
        <nav className={`fixed w-full z-50 transition-all duration-300 ${scrolled ? 'bg-background/80 backdrop-blur-md border-b shadow-sm' : 'bg-transparent'}`}>
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-16">
                    <Link to="/" className="flex items-center space-x-2 text-primary font-bold text-xl">
                        <Clapperboard className="w-8 h-8" />
                        <span>AI Story</span>
                    </Link>

                    {/* Desktop Menu */}
                    <div className="hidden md:flex items-center space-x-8">
                        <Link to="/" className="text-foreground/80 hover:text-primary transition-colors">Features</Link>
                        <Link to="/" className="text-foreground/80 hover:text-primary transition-colors">Showcase</Link>
                        <Link to="/" className="text-foreground/80 hover:text-primary transition-colors">Pricing</Link>
                        {isLoggedIn ? (
                            <div className="flex items-center space-x-4">
                                <Link to="/projects">
                                    <button className="px-4 py-2 rounded-full bg-primary/10 text-primary hover:bg-primary/20 transition-colors font-medium">
                                        Dashboard
                                    </button>
                                </Link>
                                <button onClick={handleLogout} className="text-sm text-foreground/60 hover:text-destructive transition-colors">
                                    Sign Out
                                </button>
                            </div>
                        ) : (
                            <div className="flex items-center space-x-4">
                                <Link to="/auth" className="text-foreground/80 hover:text-primary transition-colors">Log in</Link>
                                <Link to="/auth">
                                    <button className="px-6 py-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-all shadow-lg hover:shadow-primary/25 font-medium">
                                        Get Started
                                    </button>
                                </Link>
                            </div>
                        )}
                    </div>

                    {/* Mobile Menu Button */}
                    <div className="md:hidden">
                        <button onClick={() => setIsOpen(!isOpen)} className="text-foreground">
                            {isOpen ? <X /> : <Menu />}
                        </button>
                    </div>
                </div>
            </div>

            {/* Mobile Menu */}
            {isOpen && (
                <motion.div 
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="md:hidden bg-background border-b"
                >
                    <div className="px-4 pt-2 pb-6 space-y-2">
                        <Link to="/" className="block py-2 text-foreground/80">Features</Link>
                        <Link to="/" className="block py-2 text-foreground/80">Pricing</Link>
                        <hr className="border-border my-2"/>
                        {isLoggedIn ? (
                             <Link to="/projects" className="block py-2 text-primary font-semibold">Go to Dashboard</Link>
                        ) : (
                            <>
                                <Link to="/auth" className="block py-2 text-foreground/80">Log in</Link>
                                <Link to="/auth" className="block mt-2 w-full text-center px-4 py-3 bg-primary text-primary-foreground rounded-lg">Get Started</Link>
                            </>
                        )}
                    </div>
                </motion.div>
            )}
        </nav>
    );
};

export default Navbar;
