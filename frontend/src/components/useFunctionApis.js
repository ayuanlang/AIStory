import { useEffect, useState } from 'react';
import { getFunctionApiConfigs } from '../services/api';

export const useFunctionApis = () => {
    const [configs, setConfigs] = useState({});

    useEffect(() => {
        const load = async () => {
            try {
                const res = await getFunctionApiConfigs();
                const map = {};
                res.forEach(item => {
                    map[item.function_name] = item.api_settings;
                });
                setConfigs(map);
            } catch (err) {}
        };
        load();
    }, []);

    return configs;
};
