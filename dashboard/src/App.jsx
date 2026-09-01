import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { InventoryHealth } from './pages/InventoryHealth';
import { ReasoningTrace } from './pages/ReasoningTrace';
import { SapMonitor } from './pages/SapMonitor';
import { FeedbackAnalytics } from './pages/FeedbackAnalytics';

export default function App() {
  const [activeTab, setActiveTab] = useState('inventory-health');
  const [activeRole, setActiveRole] = useState('Regional Manager');

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <Navbar activeRole={activeRole} setActiveRole={setActiveRole} />

      <div className="flex flex-1">
        <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

        <main className="flex-1 p-6 overflow-y-auto max-w-7xl">
          {activeTab === 'inventory-health' && <InventoryHealth />}
          {activeTab === 'reasoning-trace' && <ReasoningTrace />}
          {activeTab === 'sap-monitor' && <SapMonitor />}
          {activeTab === 'feedback-analytics' && <FeedbackAnalytics />}
        </main>
      </div>
    </div>
  );
}
