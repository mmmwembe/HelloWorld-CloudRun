import logging
import json
from typing import List, Dict, Optional, Union, Any
import numpy as np

class SegmentationOps:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def parse_segmentation_points(self, segmentation_text: str, image_width: float, image_height: float) -> List[Dict[str, Any]]:
        """
        Parse segmentation text into point arrays.
        
        Args:
            segmentation_text (str): Raw segmentation text data
            image_width (float): Width of the image
            image_height (float): Height of the image
            
        Returns:
            List[Dict]: List of parsed segmentation points with labels
        """
        try:
            points = []
            if not segmentation_text.strip():
                return points
                
            lines = segmentation_text.strip().split('\n')
            for line in lines:
                parts = line.split(' ')
                if len(parts) < 3:  # Need at least label and one point
                    continue
                    
                label = int(parts[0])
                coords = []
                for i in range(1, len(parts), 2):
                    if i + 1 < len(parts):
                        x = float(parts[i]) * image_width
                        y = float(parts[i + 1]) * image_height
                        coords.append({'x': x, 'y': y})
                
                if coords:
                    points.append({
                        'label': label,
                        'points': coords
                    })
                    
            return points
        except Exception as e:
            self.logger.error(f"Error parsing segmentation points: {str(e)}")
            return []

    def find_matching_bbox(self, segmentation_points: List[Dict[str, float]], bboxes: List[Dict[str, Any]], overlap_threshold: float = 0.5) -> Optional[int]:
        """
        Find which bbox a segmentation belongs to based on point overlap.
        
        Args:
            segmentation_points (List[Dict]): List of segmentation points
            bboxes (List[Dict]): List of bounding boxes
            overlap_threshold (float): Minimum overlap ratio required (default: 0.5)
            
        Returns:
            Optional[int]: Index of matching bbox or None if no match found
        """
        try:
            if not segmentation_points or not bboxes:
                return None
                
            max_overlap = 0
            matching_bbox_index = None
            
            for bbox_index, bbox in enumerate(bboxes):
                bbox_coords = [float(x) for x in bbox['bbox'].split(',')]
                x1, y1, x2, y2 = bbox_coords
                
                # Count points inside this bbox
                points_inside = sum(1 for point in segmentation_points 
                                  if x1 <= point['x'] <= x2 and y1 <= point['y'] <= y2)
                                  
                overlap_ratio = points_inside / len(segmentation_points)
                
                if overlap_ratio > max_overlap:
                    max_overlap = overlap_ratio
                    matching_bbox_index = bbox_index
                    
            return matching_bbox_index if max_overlap >= overlap_threshold else None
        except Exception as e:
            self.logger.error(f"Error finding matching bbox: {str(e)}")
            return None

def align_bbox_segmentations(self, image_data: Dict[str, Any], segmentation_text: str) -> Dict[str, Any]:
    """
    Align segmentations with bounding boxes only where they properly pair.
    Segmentations without matching bboxes are ignored.
    Bboxes without matching segmentations keep empty segmentation field.
    """
    try:
        if not image_data or not segmentation_text:
            return image_data

        self.logger.info(f"Starting alignment for image: {image_data.get('image_url', 'unknown')}")
        
        image_width = float(image_data.get('image_width', 1024))
        image_height = float(image_data.get('image_height', 768))
        
        # Get all bounding boxes
        bboxes = image_data.get('info', [])
        
        # Initialize/reset all segmentation fields to empty
        for bbox in bboxes:
            bbox['segmentation'] = ""
        
        self.logger.info(f"Processing {len(bboxes)} bounding boxes")
        
        # Process each line of segmentation text
        lines = segmentation_text.strip().split('\n')
        for line in lines:
            parts = line.split(' ')
            if len(parts) < 3:  # Need at least label and one point
                continue
                
            # Get label and points
            label = parts[0]
            points = []
            for i in range(1, len(parts), 2):
                if i + 1 < len(parts):
                    x = float(parts[i]) * image_width
                    y = float(parts[i + 1]) * image_height
                    points.append(f"{x},{y}")
            
            if not points:
                continue
                
            # Try to find a matching bbox
            best_match = None
            max_overlap = 0.5  # Minimum threshold for considering a match
            
            for bbox in bboxes:
                bbox_coords = [float(x) for x in bbox['bbox'].split(',')]
                x1, y1, x2, y2 = bbox_coords
                
                # Count points inside this bbox
                points_inside = 0
                for point in points:
                    px, py = map(float, point.split(','))
                    if x1 <= px <= x2 and y1 <= py <= y2:
                        points_inside += 1
                
                overlap_ratio = points_inside / len(points)
                if overlap_ratio > max_overlap:
                    max_overlap = overlap_ratio
                    best_match = bbox
            
            # If we found a good match, store the segmentation
            if best_match is not None:
                best_match['segmentation'] = line
                self.logger.info(f"Matched segmentation to bbox {best_match.get('index')} "
                               f"with {len(points)} points and {max_overlap:.2%} overlap")
        
        # Log summary
        matched_count = sum(1 for bbox in bboxes if bbox['segmentation'])
        self.logger.info(f"Completed alignment: {matched_count} bboxes matched with segmentations "
                        f"out of {len(bboxes)} total bboxes")
        
        # Update image data
        image_data['info'] = bboxes
        return image_data
            
    except Exception as e:
        self.logger.error(f"Error aligning bbox segmentations: {str(e)}")
        return image_data

    def get_segmentation_label_text(self, label: int) -> str:
        """
        Convert numeric segmentation label to human-readable text.
        
        Args:
            label (int): Numeric label
            
        Returns:
            str: Human-readable label text
        """
        try:
            label_map = {
                0: "Incomplete",
                1: "Complete",
                2: "Fragmented", 
                3: "Blurred",
                4: "SideView"
            }
            return label_map.get(label, "Unknown")
        except Exception as e:
            self.logger.error(f"Error getting label text: {str(e)}")
            return "Unknown"

    def validate_segmentation_data(self, segmentation: Dict[str, Any]) -> bool:
        """
        Validate segmentation data structure.
        
        Args:
            segmentation (Dict): Segmentation data to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            required_fields = ['label', 'points']
            if not all(field in segmentation for field in required_fields):
                return False
                
            if not isinstance(segmentation['points'], list):
                return False
                
            if not all(isinstance(p, dict) and 'x' in p and 'y' in p 
                      for p in segmentation['points']):
                return False
                
            return True
        except Exception as e:
            self.logger.error(f"Error validating segmentation data: {str(e)}")
            return False