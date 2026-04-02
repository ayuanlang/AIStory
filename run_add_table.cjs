const fs = require('fs');
let code = fs.readFileSync('backend/app/models/all_models.py', 'utf8');

const target = "class APISetting(Base):";
const newClass = `class APIRoutingConfig(Base):
    __tablename__ = "api_routing_configs"
    id = Column(Integer, primary_key=True, index=True)
    use_function_based_routing = Column(Boolean, default=False)

class APISetting(Base):`;

code = code.replace(target, newClass);
fs.writeFileSync('backend/app/models/all_models.py', code, 'utf8');
console.log('Added APIRoutingConfig to models');