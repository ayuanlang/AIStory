import re

with open('C:/AS/AIStory/frontend/src/pages/Settings.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import
if 'InvoiceRequestModal' not in content:
    content = content.replace("import Layout from '../components/Layout';", "import Layout from '../components/Layout';\nimport InvoiceRequestModal from './components/InvoiceRequestModal';")

# 2. Add state inside Settings component
state_code = """
  // Invoice Request State
  const [invoiceModalOpen, setInvoiceModalOpen] = useState(false);
  const [selectedInvoiceOrder, setSelectedInvoiceOrder] = useState(null);
"""
if 'const [invoiceModalOpen' not in content:
    content = content.replace('const [activeTab, setActiveTab] = useState(\'profile\');', 'const [activeTab, setActiveTab] = useState(\'profile\');' + state_code)

# 3. Add modal rendering before closing </Layout>
modal_jsx = """
      {invoiceModalOpen && selectedInvoiceOrder && (
        <InvoiceRequestModal 
          orderId={selectedInvoiceOrder.id}
          amount={selectedInvoiceOrder.amount}
          onClose={() => {
            setInvoiceModalOpen(false);
            setSelectedInvoiceOrder(null);
          }}
          onSuccess={() => {
            setInvoiceModalOpen(false);
            setSelectedInvoiceOrder(null);
            fetchTransactions();
          }}
        />
      )}
"""
if '<InvoiceRequestModal' not in content:
    # Find last </Layout>
    last_layout = content.rfind('</Layout>')
    if last_layout != -1:
        content = content[:last_layout] + modal_jsx + content[last_layout:]

# 4. Bind the onClick event in the table cell
if 'onClick={() => {}}' in content:
    content = content.replace('onClick={() => {}}', 'onClick={() => { setSelectedInvoiceOrder({ id: tx.payment_order_id, amount: tx.amount }); setInvoiceModalOpen(true); }}')

with open('C:/AS/AIStory/frontend/src/pages/Settings.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Settings patched with InvoiceModal")
