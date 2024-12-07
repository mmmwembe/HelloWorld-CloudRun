// static/react/js/components/Canvas.js

const Canvas = ({
    imageUrl,
    polygons,
    currentPolygon,
    selectedSegmentIndex,
    isDrawing,
    onCanvasClick,
    onMouseMove,
    getDiatomLabel,
    containerRef,
    canvasRef,
    imageRef,
    onImageLoad
}) => {
    const drawPolygons = () => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw completed polygons
        polygons.forEach((polygon, index) => {
            if (polygon.points.length < 3) return;

            ctx.beginPath();
            ctx.moveTo(polygon.points[0].x, polygon.points[0].y);
            for (let i = 1; i < polygon.points.length; i++) {
                ctx.lineTo(polygon.points[i].x, polygon.points[i].y);
            }
            ctx.closePath();
            
            const isSelected = index === selectedSegmentIndex;
            
            if (isSelected) {
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 4;
                ctx.stroke();
                
                ctx.strokeStyle = polygon.color;
                ctx.lineWidth = 2;
                ctx.stroke();
                
                ctx.fillStyle = `${polygon.color}80`;
            } else {
                ctx.strokeStyle = polygon.color;
                ctx.lineWidth = 2;
                ctx.stroke();
                
                ctx.fillStyle = `${polygon.color}40`;
            }
            ctx.fill();
            
            if (isSelected) {
                const centerX = polygon.points.reduce((sum, p) => sum + p.x, 0) / polygon.points.length;
                const centerY = polygon.points.reduce((sum, p) => sum + p.y, 0) / polygon.points.length;
                
                ctx.font = '14px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = '#ffffff';
                ctx.strokeStyle = '#000000';
                ctx.lineWidth = 3;
                
                const text = `${index + 1}. ${getDiatomLabel(polygon.label)}`;
                ctx.strokeText(text, centerX, centerY);
                ctx.fillText(text, centerX, centerY);
            }
        });

        // Draw current polygon
        if (currentPolygon.length > 0) {
            ctx.beginPath();
            ctx.moveTo(currentPolygon[0].x, currentPolygon[0].y);
            for (let i = 1; i < currentPolygon.length; i++) {
                ctx.lineTo(currentPolygon[i].x, currentPolygon[i].y);
            }
            if (isDrawing) {
                ctx.lineTo(currentPolygon[currentPolygon.length - 1].x, currentPolygon[currentPolygon.length - 1].y);
            }
            
            ctx.strokeStyle = '#2ecc71';
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    };

    React.useEffect(() => {
        drawPolygons();
    }, [polygons, currentPolygon, selectedSegmentIndex]);

    return (
        <div 
            ref={containerRef}
            className="relative w-full max-w-4xl mt-4"
        >
            <img
                ref={imageRef}
                src={imageUrl}
                alt="Diatom"
                className="w-full"
                onLoad={() => {
                    const canvas = canvasRef.current;
                    const container = containerRef.current;
                    const image = imageRef.current;
                    
                    if (canvas && container && image) {
                        canvas.width = container.offsetWidth;
                        canvas.height = container.offsetHeight;
                        onImageLoad?.();
                        drawPolygons();
                    }
                }}
            />
            <canvas
                ref={canvasRef}
                className="absolute top-0 left-0 w-full h-full cursor-crosshair"
                onClick={onCanvasClick}
                onMouseMove={onMouseMove}
            />
        </div>
    );
};

export default Canvas;