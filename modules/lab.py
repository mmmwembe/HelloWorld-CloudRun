    def process_paper(self, full_text: str, extracted_images_file_metadata: Dict) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        """
        Process a paper's full text to extract paper info, diatoms data, and image URLs.
        
        Args:
            full_text (str): The complete text content of the paper
            
        Returns:
            tuple: (paper_info, paper_diatoms_data, paper_image_urls)
                - paper_info: Dictionary containing paper information
                - paper_diatoms_data: Dictionary containing diatoms data
                - paper_image_urls: List of image URLs from the paper
        """
        # Get paper info
        part1_prompt = self.part1_create_paper_info_json_from_pdf_text_content_prompt()
        part1_messages = self.part1_create_messages_for_paper_info_json(full_text, part1_prompt)
        paper_info = self.get_completion(part1_messages)
        
        if not paper_info or "error" in paper_info:
            logger.error("Failed to extract paper info")
            return {}, {}, []
            
        # Extract image URLs and species array
        paper_image_urls = paper_info.get("paper_image_urls", [])
        species_array = paper_info.get("diatom_species_array", [])
        
        if not paper_image_urls:
            logger.warning("No image URLs found in paper info")
        if not species_array:
            logger.warning("No species found in paper info")
            
        logger.info(f"Found {len(paper_image_urls)} images and {len(species_array)} species")
        
        # Create diatoms data for each image URL using species information
        diatoms_data_array = []
        
    
        paper_image_urls = extracted_images_file_metadata.get('paper_image_urls',[])
        image_url = paper_image_urls[0]
        # Create info entries for all species
        info_array = []
        for species in species_array:
            try:
                info_entry = {
                    "label": [f"{species['species_index']} {species['formatted_species_name']}"],
                    "index": species['species_index'],
                    "species": species['formatted_species_name'],
                    "bbox": "",
                    "yolo_bbox": "",
                    "segmentation": "",
                    "embeddings": ""
                }
                info_array.append(info_entry)
            except KeyError as e:
                logger.error(f"Missing required field in species data: {e}")
                continue
        
        if info_array:  # Only create entry if we have species info
            diatom_data = {
                "image_url": image_url,
                "image_width": "",
                "image_height": "",
                "info": info_array
            }
            diatoms_data_array.append(diatom_data)
        
        # Package the diatoms data
        paper_diatoms_data = {
            "diatoms_data": diatoms_data_array
        } if diatoms_data_array else {}
        
        if not diatoms_data_array:
            logger.warning("No diatoms data was generated")
            
        return paper_info, paper_diatoms_data, paper_image_urls