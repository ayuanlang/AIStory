# KIE Input Enum Fields Explanations

- Total deduplicated fields: 18

| field_path | page_count | enum_value_count | sample_enum_values | explanation |
|---|---:|---:|---|---|
| paths.post.input.aspect_ratio | 30 | 12 | 16:9; 1:1; 21:9; 2:3; 3:2; 3:4; 4:3; 9:16; 9:21; auto; landscape; portrait | 画面宽高比。决定输出画面的构图比例，例如 16:9、9:16、1:1。 |
| paths.post.input.character_orientation | 1 | 2 | image; video | 角色朝向或人物方向控制。用于约束角色在画面中的朝向表现。 |
| paths.post.input.duration | 26 | 13 | 10; 11; 12; 13; 14; 15; 3; 4; 5; 6; 7; 8; ...(+1) | 时长参数（秒）。用于控制生成内容的持续时长。 |
| paths.post.input.image_resolution | 2 | 3 | 1k; 2k; 4k | 图像分辨率档位。用于指定输出图像清晰度等级。 |
| paths.post.input.image_size | 8 | 1 | square | 图像尺寸参数。用于控制输出图像尺寸或比例档位。 |
| paths.post.input.mode | 3 | 5 | fun; normal; pro; spicy; std | 生成模式。用于切换不同生成策略或风格行为（如标准/创意等模式）。 |
| paths.post.input.n_frames | 5 | 3 | 10; 15; 25 | 帧数参数。通常用于视频生成，决定输出的视频帧数档位。 |
| paths.post.input.num_images | 6 | 4 | 1; 2; 3; 4 | 输出图片数量。控制一次请求返回的图片张数。 |
| paths.post.input.output_format | 4 | 2 | jpeg; png | 输出格式。指定结果文件或返回体格式（如 png、jpg、webp 等）。 |
| paths.post.input.quality | 4 | 3 | basic; high; medium | 质量档位。控制生成质量与速度成本的平衡。 |
| paths.post.input.resolution | 26 | 8 | 1080p; 1k; 2k; 480p; 512p; 580p; 720p; 768p | 视频/图像分辨率。决定输出清晰度（如 720p、1080p）。 |
| paths.post.input.safety_tolerance | 1 | 7 | 0; 1; 2; 3; 4; 5; 6 | 安全容忍度。控制内容安全过滤的严格程度。 |
| paths.post.input.size | 1 | 3 | 1:1; 2:3; 3:2 | 通用尺寸参数。用于指定输出大小或比例。 |
| paths.post.input.style | 4 | 5 | AUTO; DESIGN; FICTION; GENERAL; REALISTIC | 风格参数。用于约束输出的视觉或叙事风格。 |
| paths.post.input.upscale_factor | 2 | 4 | 1; 2; 4; 8 | 放大倍数。用于上采样或超分，控制分辨率提升比例。 |
| paths.post.input.voice | 2 | 135 | 0SpgpJ4D3MpHCiWdyTg3; 1KFdM0QCwQn4rmn5nn9C; 1SM7GgM6IMuvQlz2BwM3; 1U02n4nD6AdIZ9CjF053; 1cxc5c3E9K6F1wlqOJGV; 1hlpeD1ydbI2ow0Tt3EW; 1wGbFxmAM3Fgw63G1zZJ; 2zRM7PkgwBPiau2jvVXc; 4YYIPFl9wE5c4L2eu2Gb; 56AoDkrOh6qfVPDXZ7Pt; 5l5f8iK3YPeGga21rQIX; 6F5Zhi321D3Oq7v1oNT4; ...(+123) | 音色/语音选择。用于指定语音合成时使用的声音 ID 或音色标签。 |
| paths.post.model | 79 | 79 | bytedance/seedance-1.5-pro; bytedance/seedream; bytedance/seedream-v4-edit; bytedance/seedream-v4-text-to-image; bytedance/v1-lite-image-to-video; bytedance/v1-lite-text-to-video; bytedance/v1-pro-fast-image-to-video; bytedance/v1-pro-image-to-video; bytedance/v1-pro-text-to-video; elevenlabs/audio-isolation; elevenlabs/speech-to-text; elevenlabs/text-to-speech-multilingual-v2; ...(+67) | 模型标识。用于指定调用的具体模型路由，直接决定能力、价格和可用参数集合。 |
| paths.post.reasoning_effort | 5 | 2 | high; low | 推理强度档位。用于控制模型在回答时的推理深度与耗时，通常在速度与质量之间做权衡。 |
