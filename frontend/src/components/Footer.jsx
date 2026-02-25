
import React from 'react';
import { getUiLang, tUI } from '../lib/uiLang';

const Footer = () => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    return (
        <footer className="bg-muted/30 border-t py-12">
            <div className="max-w-7xl mx-auto px-4 grid grid-cols-1 md:grid-cols-4 gap-8">
                <div className="col-span-1 md:col-span-1">
                    <h3 className="font-bold text-lg mb-4 text-primary">AI Story</h3>
                    <p className="text-sm text-muted-foreground">
                        {t('用 AI 驱动的可视化工具赋能创作者。', 'Empowering storytellers with AI-driven visualization tools.')}
                        {t('从剧本到画面，只需几分钟。', 'From script to screen in minutes.')}
                    </p>
                </div>
                <div>
                    <h4 className="font-semibold mb-4">{t('产品', 'Product')}</h4>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                        <li><a href="#" className="hover:text-primary transition-colors">{t('功能', 'Features')}</a></li>
                        <li><a href="#" className="hover:text-primary transition-colors">{t('集成', 'Integrations')}</a></li>
                        <li><a href="#" className="hover:text-primary transition-colors">{t('价格', 'Pricing')}</a></li>
                    </ul>
                </div>
                <div>
                    <h4 className="font-semibold mb-4">{t('资源', 'Resources')}</h4>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                        <li><a href="#" className="hover:text-primary transition-colors">{t('文档', 'Documentation')}</a></li>
                        <li><a href="#" className="hover:text-primary transition-colors">{t('博客', 'Blog')}</a></li>
                        <li><a href="#" className="hover:text-primary transition-colors">{t('社区', 'Community')}</a></li>
                    </ul>
                </div>
                <div>
                    <h4 className="font-semibold mb-4">{t('法律', 'Legal')}</h4>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                        <li>{t('隐私政策', 'Privacy Policy')}</li>
                        <li>{t('服务条款', 'Terms of Service')}</li>
                    </ul>
                </div>
            </div>
            <div className="max-w-7xl mx-auto px-4 mt-12 pt-8 border-t text-center text-sm text-muted-foreground">
                {t('© 2026 AI Story Inc. 保留所有权利。', '© 2026 AI Story Inc. All rights reserved.')}
            </div>
        </footer>
    );
};

export default Footer;
