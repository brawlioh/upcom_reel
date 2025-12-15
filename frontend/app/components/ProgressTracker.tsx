'use client'

import { CheckCircle, Circle, Loader2, Video, Monitor, Image, Settings, AlertCircle, ExternalLink, Eye } from 'lucide-react'
import { useAutomation } from '../hooks/useAutomation'
import { useError } from '../contexts/ErrorContext'

interface ProgressTrackerProps {
  currentStep: number
  totalSteps: number
  isRunning: boolean
}

const steps = [
  {
    id: 1,
    name: 'Intro Generation',
    description: 'Creating intro video with HeyGen',
    icon: Video,
    color: 'text-blue-400'
  },
  {
    id: 2,
    name: 'Gameplay Processing',
    description: 'Processing gameplay clip with Vizard',
    icon: Monitor,
    color: 'text-green-400'
  },
  {
    id: 3,
    name: 'Cover Photo',
    description: 'Creating price comparison banner',
    icon: Image,
    color: 'text-purple-400'
  },
  {
    id: 4,
    name: 'Final Compilation',
    description: 'Compiling final reel with Creatomate',
    icon: Settings,
    color: 'text-orange-400'
  }
]

export default function ProgressTracker({ currentStep, totalSteps, isRunning }: ProgressTrackerProps) {
  const { currentJob, isConnected } = useAutomation()
  const { showError } = useError()
  
  // Use real job data if available, otherwise fall back to props
  const actualCurrentStep = currentJob?.current_step || currentStep
  const actualTotalSteps = currentJob?.total_steps || totalSteps
  const actualIsRunning = currentJob?.status === 'running' || currentJob?.status === 'queued' || isRunning
  const progress = currentJob?.progress || (actualCurrentStep > 0 ? (actualCurrentStep / actualTotalSteps) * 100 : 0)
  
  // Job is completed if status is 'completed' OR if progress is 100%
  const isJobCompleted = currentJob?.status === 'completed' || progress >= 100

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-lg font-semibold text-white">Pipeline Progress</h3>
        <div className="text-sm text-dark-400">
          {actualCurrentStep > 0 ? `${actualCurrentStep}/${actualTotalSteps}` : 'Ready'}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-1.5">
        <div className="flex justify-between text-sm text-dark-400 mb-1.5">
          <span>Progress</span>
          <span>{Math.round(progress)}%</span>
        </div>
        <div className="w-full bg-dark-700 rounded-full h-2">
          <div
            className="bg-primary-600 h-2 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
      </div>

      {/* Steps */}
      <div className="space-y-0.5">
        {steps.map((step) => {
          // Mark step as completed if: current_step > step.id OR job is completed (status or 100% progress)
          const isCompleted = actualCurrentStep > step.id || (isJobCompleted && step.id <= actualCurrentStep)
          const isCurrent = actualCurrentStep === step.id && actualIsRunning && !isJobCompleted
          const isPending = actualCurrentStep < step.id && !isJobCompleted
          
          // Check for module-specific errors
          const hasFailed = currentJob?.status === 'failed' && 
                           currentJob?.current_step === step.id;
          
          return (
            <div
              key={step.id}
              className={`flex items-center space-x-3 p-2 rounded-lg transition-colors ${
                hasFailed ? 'bg-red-600/10 border border-red-600/20' :
                isCurrent ? 'bg-primary-600/10 border border-primary-600/20' : 
                isCompleted ? 'bg-green-600/10' : 'bg-dark-700/50'
              }`}
            >
              <div className="flex-shrink-0">
                {hasFailed ? (
                  <AlertCircle className="w-5 h-5 text-red-400" />
                ) : isCompleted ? (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                ) : isCurrent ? (
                  <Loader2 className="w-5 h-5 text-primary-400 animate-spin" />
                ) : (
                  <Circle className="w-5 h-5 text-dark-500" />
                )}
              </div>
              
              <div className="flex-shrink-0">
                <step.icon className={`w-4 h-4 ${
                  hasFailed ? 'text-red-400' :
                  isCompleted ? 'text-green-400' :
                  isCurrent ? 'text-primary-400' :
                  step.color
                }`} />
              </div>
              
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium ${
                  hasFailed ? 'text-red-400' :
                  isCompleted ? 'text-green-400' :
                  isCurrent ? 'text-primary-400' :
                  'text-white'
                }`}>
                  {step.name}
                </p>
                <p className="text-xs text-dark-400 truncate">
                  {hasFailed ? (
                    <span className="text-red-400">Failed: {currentJob?.error_message?.split(':')[0] || 'Error in processing'}</span>
                  ) : step.description}
                </p>
              </div>
              
              <div className="flex-shrink-0">
                {isCurrent && (
                  <div className="flex space-x-1">
                    <div className="w-1 h-1 bg-primary-400 rounded-full animate-bounce"></div>
                    <div className="w-1 h-1 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                    <div className="w-1 h-1 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Status Message */}
      {actualIsRunning && (
        <div className="mt-4 p-3 bg-primary-600/10 border border-primary-600/20 rounded-lg">
          <p className="text-sm text-primary-400">
            {currentJob?.step_name || (actualCurrentStep > 0 && actualCurrentStep <= steps.length
              ? `Processing: ${steps[actualCurrentStep - 1].description}`
              : 'Initializing automation pipeline...')
            }
          </p>
        </div>
      )}

      {/* Job Status */}
      {currentJob && currentJob.status === 'completed' && (
        <div className="mt-4 p-4 bg-green-600/10 border border-green-600/20 rounded-lg">
          <div className="flex items-start">
            <CheckCircle className="w-5 h-5 text-green-400 mt-0.5 mr-2 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-green-400 mb-3">
                Automation completed successfully!
              </p>
              
              {currentJob.result_path && (
                <div className="space-y-3">
                  {/* Video URL Display */}
                  <div className="bg-dark-800/50 rounded-lg p-3 border border-green-600/10">
                    <div className="flex items-center space-x-2 mb-2">
                      <Video className="w-4 h-4 text-green-400" />
                      <span className="text-sm font-medium text-white">Final Video URL</span>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <div className="flex-1 min-w-0">
                        <a 
                          href={currentJob.result_path} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-xs text-blue-400 hover:text-blue-300 transition-colors break-all"
                        >
                          {currentJob.result_path}
                        </a>
                      </div>
                      <button
                        onClick={() => navigator.clipboard.writeText(currentJob.result_path)}
                        className="px-2 py-1 text-xs bg-green-600/20 hover:bg-green-600/30 text-green-400 rounded transition-colors"
                      >
                        Copy
                      </button>
                      <a
                        href={currentJob.result_path}
                        target="_blank"
                        rel="noopener noreferrer" 
                        className="p-1 text-green-400 hover:text-green-300 transition-colors"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    </div>
                  </div>
                  
                  {/* Video Preview */}
                  <div className="bg-dark-800/50 rounded-lg p-3 border border-green-600/10">
                    <div className="flex items-center space-x-2 mb-3">
                      <Eye className="w-4 h-4 text-green-400" />
                      <span className="text-sm font-medium text-white">Video Preview</span>
                    </div>
                    
                    <div className="relative">
                      <video 
                        controls 
                        className="w-full max-w-md mx-auto rounded-lg bg-black"
                        preload="metadata"
                      >
                        <source src={currentJob.result_path} type="video/mp4" />
                        Your browser does not support the video tag.
                      </video>
                    </div>
                  </div>
                </div>
              )}
              
              <p className="text-xs text-dark-400 mt-3 italic">
                Your YouTube Reel is ready! You can preview it above or open the URL in a new tab.
              </p>
            </div>
          </div>
        </div>
      )}

      {currentJob && currentJob.status === 'failed' && (
        <div className="mt-4 p-3 bg-red-600/10 border border-red-600/20 rounded-lg">
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 mr-2 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-400">
                Automation Failed
              </p>
              <p className="text-sm text-red-300 whitespace-pre-wrap mt-1">
                {currentJob.error_message}
              </p>
              
              <div className="mt-3 flex items-center space-x-3">
                <button 
                  className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white text-xs font-medium rounded-md transition-colors"
                  onClick={() => {
                    // Show error details in modal
                    showError('Error Details', `${currentJob.error_message}\n\nModule: ${steps[currentJob.current_step - 1]?.name || 'Unknown'}\nJob ID: ${currentJob.job_id}`)
                  }}
                >
                  View Details
                </button>
                
                <button 
                  className="px-3 py-1 bg-dark-600 hover:bg-dark-700 text-white text-xs font-medium rounded-md transition-colors"
                  onClick={() => {
                    window.location.reload()
                  }}
                >
                  Restart App
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
