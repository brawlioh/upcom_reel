'use client'

import { useState, useEffect } from 'react'
import { Video } from 'lucide-react'
import { useAutomation } from './hooks/useAutomation'
import AutomationControl from './components/AutomationControl'
import ProgressTracker from './components/ProgressTracker'
import JobHistory from './components/JobHistory'

export default function Home() {
  const [isRunning, setIsRunning] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [totalSteps] = useState(4) // Set to 4 steps including price comparison banner
  const { jobs, fetchAllJobs } = useAutomation()


  // Fetch jobs on component mount
  useEffect(() => {
    fetchAllJobs()
  }, [fetchAllJobs])

  return (
    <div className="min-h-screen bg-gradient-to-br from-dark-900 via-dark-800 to-dark-900 hide-connection-alerts">
      {/* Header */}
      <header className="border-b border-dark-700 bg-dark-800/50 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-6">
          <div className="flex items-center justify-between h-10">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                <Video className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">YouTube Reels Automation</h1>
                <p className="text-sm text-dark-400">Gaming Content Pipeline</p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <div className="flex items-center space-x-1 text-sm text-dark-400">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span>System Ready</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-6 py-3">
        {/* Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Left Column: Controls + Progress */}
          <div className="lg:col-span-2 space-y-2.5">
            {/* Automation Control */}
            <AutomationControl 
              isRunning={isRunning}
              setIsRunning={setIsRunning}
              setCurrentStep={setCurrentStep}
            />

            {/* Progress Tracker */}
            <ProgressTracker 
              currentStep={currentStep}
              totalSteps={totalSteps}
              isRunning={isRunning}
            />
          </div>

          {/* Right Column: Job History */}
          <div className="lg:col-span-1">
            <JobHistory />
          </div>
        </div>
      </main>
    </div>
  )
}
