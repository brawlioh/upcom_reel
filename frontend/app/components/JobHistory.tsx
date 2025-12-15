'use client'

import { useState, useEffect, useRef } from 'react'
import { Clock, CheckCircle, XCircle, Loader2, ExternalLink, Play, Video } from 'lucide-react'
import { useAutomation, type AutomationJob } from '../hooks/useAutomation'

export default function JobHistory() {
  const { jobs, currentJob, fetchAllJobs } = useAutomation()
  const [selectedJob, setSelectedJob] = useState<AutomationJob | null>(null)
  const [showPreview, setShowPreview] = useState(false)
  const prevStatusRef = useRef<string | undefined>(undefined)

  // Auto-refresh and auto-select when job completes
  useEffect(() => {
    if (currentJob) {
      // Check if job just completed (status changed to completed)
      if (currentJob.status === 'completed' && prevStatusRef.current !== 'completed') {
        // Auto-refresh job list
        fetchAllJobs()
        // Auto-select the completed job
        setSelectedJob(currentJob)
        setShowPreview(false)
      }
      prevStatusRef.current = currentJob.status
    }
  }, [currentJob?.status, currentJob?.job_id, fetchAllJobs])

  // Update selected job when currentJob updates (for real-time sync)
  useEffect(() => {
    if (selectedJob && currentJob && selectedJob.job_id === currentJob.job_id) {
      setSelectedJob(currentJob)
    }
  }, [currentJob])

  // Get the video URL (prefer online_url, fallback to result_path)
  const getVideoUrl = (job: AutomationJob): string | undefined => {
    return job.online_url || job.result_path
  }

  // Combine current job with historical jobs, avoiding duplicates
  const allJobs = currentJob 
    ? [currentJob, ...jobs.filter(j => j.job_id !== currentJob.job_id)]
    : jobs

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-400" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-400" />
      case 'running':
      case 'queued':
        return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
      default:
        return <Clock className="w-4 h-4 text-dark-400" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-600/10 border-green-600/20'
      case 'failed':
        return 'bg-red-600/10 border-red-600/20'
      case 'running':
      case 'queued':
        return 'bg-blue-600/10 border-blue-600/20'
      default:
        return 'bg-dark-700/50 border-dark-600/20'
    }
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A'
    try {
      const date = new Date(dateString)
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return 'N/A'
    }
  }

  return (
    <div className="card h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
          <Clock className="w-5 h-5 text-primary-400" />
          <span>Job History</span>
        </h3>
        <button
          onClick={() => fetchAllJobs()}
          className="text-xs text-dark-400 hover:text-white transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Job List */}
      <div className="flex-1 overflow-y-auto space-y-2 min-h-0 max-h-[400px]">
        {allJobs.length === 0 ? (
          <div className="text-center py-8 text-dark-400">
            <Video className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No jobs yet</p>
            <p className="text-xs mt-1">Start an automation to see history here</p>
          </div>
        ) : (
          allJobs.map((job) => (
            <div
              key={job.job_id}
              className={`p-3 rounded-lg border cursor-pointer transition-all hover:scale-[1.01] ${getStatusColor(job.status)} ${
                selectedJob?.job_id === job.job_id ? 'ring-2 ring-primary-500' : ''
              }`}
              onClick={() => setSelectedJob(job)}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-2 min-w-0 flex-1">
                  {getStatusIcon(job.status)}
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-white truncate">
                      {job.game_title || `Steam App ${job.steam_app_id}` || 'Unknown Game'}
                    </p>
                    <p className="text-xs text-dark-400">
                      {job.status === 'running' ? (
                        <span className="text-blue-400">
                          Step {job.current_step}/4 • {job.progress || 0}%
                        </span>
                      ) : job.status === 'completed' ? (
                        <span className="text-green-400">Completed</span>
                      ) : job.status === 'failed' ? (
                        <span className="text-red-400">Failed</span>
                      ) : (
                        <span>{job.status}</span>
                      )}
                    </p>
                  </div>
                </div>
                <span className="text-xs text-dark-500 whitespace-nowrap ml-2">
                  {formatDate(job.created_at)}
                </span>
              </div>

              {/* Progress bar for running jobs */}
              {(job.status === 'running' || job.status === 'queued') && (
                <div className="mt-2">
                  <div className="w-full bg-dark-700 rounded-full h-1.5">
                    <div
                      className="bg-blue-500 h-1.5 rounded-full transition-all duration-500"
                      style={{ width: `${job.progress || 0}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Selected Job Details */}
      {selectedJob && (
        <div className="mt-3 pt-3 border-t border-dark-700">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-medium text-white">Job Details</h4>
            <button
              onClick={() => setSelectedJob(null)}
              className="text-xs text-dark-400 hover:text-white"
            >
              Close
            </button>
          </div>
          
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-dark-400">Job ID:</span>
              <span className="text-white font-mono truncate ml-2 max-w-[150px]">
                {selectedJob.job_id}
              </span>
            </div>
            
            <div className="flex justify-between">
              <span className="text-dark-400">Status:</span>
              <span className={`font-medium ${
                selectedJob.status === 'completed' ? 'text-green-400' :
                selectedJob.status === 'failed' ? 'text-red-400' :
                selectedJob.status === 'running' ? 'text-blue-400' : 'text-white'
              }`}>
                {selectedJob.status}
              </span>
            </div>

            {selectedJob.step_name && (
              <div className="flex justify-between">
                <span className="text-dark-400">Current Step:</span>
                <span className="text-white">{selectedJob.step_name}</span>
              </div>
            )}

            {selectedJob.error_message && (
              <div className="mt-2 p-2 bg-red-600/10 border border-red-600/20 rounded text-red-400">
                {selectedJob.error_message}
              </div>
            )}

            {/* Video Preview & Actions */}
            {selectedJob.status === 'completed' && getVideoUrl(selectedJob) && (
              <div className="mt-3 space-y-2">
                {/* Video URL Display */}
                <div className="p-2 bg-dark-700/50 rounded text-xs break-all">
                  <span className="text-dark-400">URL: </span>
                  <span className="text-blue-400">{getVideoUrl(selectedJob)}</span>
                </div>

                <button
                  onClick={() => setShowPreview(!showPreview)}
                  className="w-full flex items-center justify-center space-x-2 px-3 py-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  <Play className="w-4 h-4" />
                  <span>{showPreview ? 'Hide Preview' : 'Show Preview'}</span>
                </button>

                {showPreview && (
                  <div className="mt-2">
                    <video 
                      controls 
                      autoPlay
                      className="w-full rounded-lg bg-black"
                      preload="auto"
                      crossOrigin="anonymous"
                    >
                      <source src={getVideoUrl(selectedJob)} type="video/mp4" />
                      Your browser does not support the video tag.
                    </video>
                  </div>
                )}

                <div className="flex space-x-2">
                  <a
                    href={getVideoUrl(selectedJob)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 flex items-center justify-center space-x-1 px-3 py-1.5 bg-green-600/20 hover:bg-green-600/30 text-green-400 text-xs font-medium rounded transition-colors"
                  >
                    <ExternalLink className="w-3 h-3" />
                    <span>Open URL</span>
                  </a>
                  <button
                    onClick={() => {
                      const url = getVideoUrl(selectedJob)
                      if (url) {
                        navigator.clipboard.writeText(url)
                          .then(() => alert('URL copied to clipboard!'))
                          .catch(() => alert('Failed to copy URL'))
                      }
                    }}
                    className="flex-1 px-3 py-1.5 bg-dark-600 hover:bg-dark-500 text-white text-xs font-medium rounded transition-colors"
                  >
                    Copy URL
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
