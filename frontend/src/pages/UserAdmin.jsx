import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';
import { Shield, User, Key, Check, X, Crown, Settings } from 'lucide-react';

const UserAdmin = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [currentUser, setCurrentUser] = useState(null);

    // Fetch users (requires superuser)
    const fetchUsers = async () => {
        try {
            setLoading(true);
            // Use axios api instance
            try {
                const response = await api.get('/users');
                setUsers(response.data);
                setLoading(false);
            } catch (err) {
                 if (err.response && err.response.status === 403) {
                    setError("Access Denied: You must be a superuser to view this page.");
                 } else {
                    setError(err.message || "Failed to fetch users");
                 }
                 setLoading(false);
            }
        } catch (e) {
            setError(e.message);
            setLoading(false);
        }
    };

    // Update user permission
    const updateUser = async (userId, data) => {
        try {
            const response = await api.put(`/users/${userId}`, data);
            
            // Refund list
            const updated = response.data;
            setUsers(users.map(u => u.id === userId ? { ...u, ...updated } : u));
            
            if (data.is_system) {
                 // Refresh mostly because others might have been unset
                 fetchUsers();
            }

        } catch (e) {
            console.error(e);
            alert(e.message || "Update failed");
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    const Toggle = ({ active, onClick, color = "bg-green-500", label }) => (
        <button 
            onClick={onClick}
            className={`
                relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-primary
                ${active ? color : 'bg-gray-700'}
            `}
            title={label}
        >
            <span
                className={`${
                    active ? 'translate-x-6' : 'translate-x-1'
                } inline-block h-4 w-4 transform rounded-full bg-white transition-transform`}
            />
        </button>
    );

    if (error) {
         return (
             <div className="min-h-screen bg-[#09090b] text-white flex flex-col">
                <Navbar />
                <div className="flex-1 flex items-center justify-center">
                    <div className="bg-red-500/10 border border-red-500/50 p-8 rounded-xl text-center">
                        <Shield className="w-12 h-12 text-red-500 mx-auto mb-4" />
                        <h2 className="text-xl font-bold mb-2">Access Resticted</h2>
                        <p className="text-red-200">{error}</p>
                    </div>
                </div>
                <Footer />
             </div>
         )
    }

    return (
        <div className="min-h-screen bg-[#09090b] text-white flex flex-col font-sans">
            <Navbar />
            
            <main className="flex-1 container mx-auto px-4 py-8">
                <div className="flex justify-between items-center mb-8">
                    <div>
                        <h1 className="text-2xl font-bold flex items-center gap-2">
                             <Shield className="w-6 h-6 text-primary" /> 
                             User Administration
                        </h1>
                        <p className="text-muted-foreground text-sm mt-1">Manage user permissions and system roles.</p>
                    </div>
                    
                    <button onClick={fetchUsers} className="px-4 py-2 bg-white/5 hover:bg-white/10 rounded-md text-sm border border-white/10">
                        Refresh List
                    </button>
                </div>

                {loading ? (
                    <div className="flex justify-center py-20">
                         <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    </div>
                ) : (
                    <div className="bg-[#121214] border border-white/10 rounded-xl overflow-hidden shadow-xl">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="border-b border-white/10 bg-white/5 text-xs uppercase text-muted-foreground">
                                    <th className="p-4 w-16 text-center">ID</th>
                                    <th className="p-4">User</th>
                                    <th className="p-4 text-center w-32">Active</th>
                                    <th className="p-4 text-center w-32">Authorized</th>
                                    <th className="p-4 text-center w-32">System</th>
                                    <th className="p-4 text-center w-32">Superuser</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {users.map(user => (
                                    <tr key={user.id} className="hover:bg-white/[0.02] transition-colors">
                                        <td className="p-4 text-center text-muted-foreground font-mono text-xs">{user.id}</td>
                                        <td className="p-4">
                                            <div className="flex items-center gap-3">
                                                 <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500/20 to-blue-500/20 flex items-center justify-center border border-white/10">
                                                     {user.is_superuser ? <Crown className="w-3 h-3 text-yellow-500" /> : <User className="w-3 h-3 text-primary" />}
                                                 </div>
                                                 <div>
                                                     <div className="font-medium text-white flex items-center gap-2">
                                                         {user.username}
                                                         {user.is_system && <span className="px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-400 text-[10px] font-bold border border-blue-500/30">SYSTEM</span>}
                                                     </div>
                                                     <div className="text-xs text-muted-foreground">{user.email || 'No email'}</div>
                                                 </div>
                                            </div>
                                        </td>
                                        <td className="p-4 text-center">
                                            <Toggle 
                                                active={user.is_active} 
                                                onClick={() => updateUser(user.id, { is_active: !user.is_active })}
                                                label="Can Login"
                                            />
                                        </td>
                                        <td className="p-4 text-center">
                                            <Toggle 
                                                active={user.is_authorized} 
                                                onClick={() => updateUser(user.id, { is_authorized: !user.is_authorized })} 
                                                color="bg-purple-600"
                                                label="Can use System APIs"
                                            />
                                            <div className="text-[10px] mt-1 text-muted-foreground">Reuse API Keys</div>
                                        </td>
                                        <td className="p-4 text-center">
                                            <Toggle 
                                                active={user.is_system} 
                                                onClick={() => updateUser(user.id, { is_system: !user.is_system })} 
                                                color="bg-blue-600"
                                                label="Is System Provider"
                                            />
                                            <div className="text-[10px] mt-1 text-muted-foreground">Provides Keys</div>
                                        </td>
                                        <td className="p-4 text-center">
                                             <Toggle 
                                                active={user.is_superuser} 
                                                onClick={() => updateUser(user.id, { is_superuser: !user.is_superuser })} 
                                                color="bg-red-600"
                                                label="Is Admin"
                                            />
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
                
                <div className="mt-6 text-xs text-muted-foreground grid gap-2 p-4 border border-white/5 rounded-lg bg-white/[0.02]">
                    <h3 className="font-bold text-white mb-1 flex items-center gap-2"><Settings className="w-3 h-3"/> Policy Reference</h3>
                    <div className="flex items-start gap-2">
                        <Check className="w-3 h-3 mt-0.5 text-green-500" />
                        <span><strong>Active:</strong> Basic login permission.</span>
                    </div>
                    <div className="flex items-start gap-2">
                        <Check className="w-3 h-3 mt-0.5 text-purple-500" />
                        <span><strong>Authorized:</strong> Can create content using "System" user's API keys if their own are missing.</span>
                    </div>
                    <div className="flex items-start gap-2">
                        <Check className="w-3 h-3 mt-0.5 text-blue-500" />
                        <span><strong>System:</strong> The single account whose API keys are shared with Authorized users. Only one System user should exist.</span>
                    </div>
                    <div className="flex items-start gap-2">
                        <Check className="w-3 h-3 mt-0.5 text-red-500" />
                        <span><strong>Superuser:</strong> Can access this admin panel and modify other users.</span>
                    </div>
                </div>

            </main>
        </div>
    );
};

export default UserAdmin;
