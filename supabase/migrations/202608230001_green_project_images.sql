update green_projects
set image_path = case slug
  when 'illawarra-community-battery' then '/green-projects/illawarra-community-battery.webp'
  when 'social-housing-solar' then '/green-projects/social-housing-solar.webp'
  when 'coastal-habitat-restoration' then '/green-projects/coastal-habitat-restoration.webp'
  else image_path
end
where slug in (
  'illawarra-community-battery',
  'social-housing-solar',
  'coastal-habitat-restoration'
);
