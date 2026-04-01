content = open('src/pages/ProjectList.jsx', 'r', encoding='utf-8').read()

content = content.replace(
    'const [newDescription, setNewDescription] = useState('''');',
    'const [newDescription, setNewDescription] = useState('''');\n  const [newHasExistingAssets, setNewHasExistingAssets] = useState(false);'
)

content = content.replace(
    'is_template: false,',
    'is_template: false,\n        has_existing_assets: newHasExistingAssets,'
)

content = content.replace(
    '                {/* Title */}',
    '''
                {/* Has Existing Assets */}
                <div className="flex items-center space-x-3 mb-6">
                  <input
                    type="checkbox"
                    id="hasExistingAssets"
                    checked={newHasExistingAssets}
                    onChange={(e) => setNewHasExistingAssets(e.target.checked)}
                    className="w-4 h-4 rounded border-white/20 bg-black/40 text-primary focus:ring-primary focus:ring-offset-gray-900"
                  />
                  <label htmlFor="hasExistingAssets" className="text-sm font-medium text-white/90 cursor-pointer">
                    已有原片、素材等内容 (Has existing assets)
                  </label>
                </div>
                {/* Title */}
    '''
)

open('src/pages/ProjectList.jsx', 'w', encoding='utf-8').write(content)
print("done")
