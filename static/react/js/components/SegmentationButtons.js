// static/react/js/components/SegmentationButtons.js

const SegmentationButtons = ({ 
    onSave, 
    onUpdate, 
    onDownload, 
    isSaving, 
    isUpdating,
    saveProgress,
    hasSegmentations 
}) => {
    return (
        <div className="flex justify-center space-x-4">
            {/* Save Button */}
            <button 
                onClick={onSave}
                disabled={isSaving}
                className={`
                    px-8 py-3 rounded-lg font-bold transform transition-all duration-200
                    flex items-center justify-center min-w-[120px]
                    ${isSaving 
                        ? 'bg-gray-400 cursor-not-allowed'
                        : 'bg-green-600 text-white hover:bg-green-500 hover:scale-105 hover:shadow-lg'
                    }
                `}
            >
                {isSaving ? (
                    <div className="flex items-center space-x-2">
                        <CircularProgress progress={saveProgress} />
                        <span className="text-white">Saving...</span>
                    </div>
                ) : (
                    <span>Save</span>
                )}
            </button>

            {/* Update Button */}
            <button 
                onClick={onUpdate}
                disabled={!hasSegmentations || isUpdating}
                className={`
                    px-8 py-3 rounded-lg font-bold transform transition-all duration-200
                    flex items-center justify-center min-w-[180px]
                    ${(!hasSegmentations || isUpdating)
                        ? 'bg-gray-400 cursor-not-allowed'
                        : 'bg-blue-600 text-white hover:bg-blue-500 hover:scale-105 hover:shadow-lg'
                    }
                `}
            >
                {isUpdating ? (
                    <div className="flex items-center space-x-2">
                        <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span>Updating...</span>
                    </div>
                ) : (
                    <div className="flex items-center space-x-2">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        <span>Update Segmentation Data</span>
                    </div>
                )}
            </button>

            {/* Download Button */}
            <button 
                onClick={onDownload}
                className="
                    bg-yellow-400 text-black px-8 py-3 rounded-lg font-bold
                    transform transition-all duration-200 
                    hover:scale-105 hover:bg-yellow-300 hover:shadow-lg
                    flex items-center space-x-2
                "
            >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                <span>Download</span>
            </button>
        </div>
    );
};

// Add PropTypes for better documentation and runtime checking
SegmentationButtons.propTypes = {
    onSave: PropTypes.func.isRequired,
    onUpdate: PropTypes.func.isRequired,
    onDownload: PropTypes.func.isRequired,
    isSaving: PropTypes.bool.isRequired,
    isUpdating: PropTypes.bool.isRequired,
    saveProgress: PropTypes.number.isRequired,
    hasSegmentations: PropTypes.bool.isRequired
};

// Add default props
SegmentationButtons.defaultProps = {
    isSaving: false,
    isUpdating: false,
    saveProgress: 0,
    hasSegmentations: false
};

export default SegmentationButtons;