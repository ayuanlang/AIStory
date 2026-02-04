
import os

path = r'c:\storyboard\AIStory\frontend\src\services\api.js'
try:
    with open(path, 'a', encoding='utf-8') as f:
        f.write("""

// --- Assets ---
export const fetchAssets = async (type = null) => {
    const params = type ? { type } : {};
    const response = await api.get('/assets/', { params });
    return response.data;
};

export const createAsset = async (data) => {
    const response = await api.post('/assets/', data);
    return response.data;
};

export const uploadAsset = async (formData) => {
    const response = await api.post('/assets/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const deleteAsset = async (id) => {
    const response = await api.delete(`/assets/${id}`);
    return response.data;
};

export const updateAsset = async (id, data) => {
    const response = await api.put(`/assets/${id}`, data);
    return response.data;
};
""")
    print("Success")
except Exception as e:
    print(e)
