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
        Align segmentations with bounding boxes for a single image.
        
        Args:
            image_data (Dict): Current image data including bboxes
            segmentation_text (str): Raw segmentation text data
            
        Returns:
            Dict: Updated image data with aligned segmentations
        """
        try:
            if not image_data or not segmentation_text:
                return image_data

            image_width = float(image_data.get('image_width', 1024))
            image_height = float(image_data.get('image_height', 768))
            
            # Parse segmentation points
            segmentation_points = self.parse_segmentation_points(
                segmentation_text,
                image_width,
                image_height
            )
            
            # Get bounding boxes
            bboxes = image_data.get('info', [])
            
            # Match segmentations to bboxes
            for seg_point_set in segmentation_points:
                matching_bbox_index = self.find_matching_bbox(
                    seg_point_set['points'],
                    bboxes
                )
                
                if matching_bbox_index is not None:
                    # Initialize segmentation array if needed
                    if 'segmentation' not in bboxes[matching_bbox_index]:
                        bboxes[matching_bbox_index]['segmentation'] = []
                        
                    # Add segmentation points to bbox
                    bboxes[matching_bbox_index]['segmentation'].append({
                        'label': seg_point_set['label'],
                        'points': seg_point_set['points']
                    })
            
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