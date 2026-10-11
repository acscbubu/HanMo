#pragma once

#include <cctype>
#include <string>
#include <vector>

namespace airphoto {

struct DeletionPlan {
  bool valid = false;
  bool removeCaches = false;
  std::string original;
  std::string view;
  std::string landscapeView;
  std::string thumb;
};

inline std::string cacheKey(std::string name) {
  for (char& ch : name) ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
  return name;
}

inline DeletionPlan deletionPlan(const std::vector<std::string>& photos, const int index) {
  DeletionPlan result;
  if (index < 0 || index >= static_cast<int>(photos.size())) return result;
  const std::string& name = photos[index];
  if (name.empty() || name.size() > 255 || name[0] == '.' ||
      name.find_first_of("/\\:") != std::string::npos || name.find("..") != std::string::npos) return result;
  result.valid = true;
  result.original = "/AirPhoto/" + name;
  // Include the original extension so A.jpg and A.png never share a cache.
  // FAT names are case-insensitive: preserve the cache if another original
  // differs only in case, even if the card can expose both directory entries.
  const std::string key = cacheKey(name);
  result.removeCaches = true;
  for (size_t i = 0; i < photos.size(); ++i) {
    if (static_cast<int>(i) != index && cacheKey(photos[i]) == key) {
      result.removeCaches = false;
      break;
    }
  }
  result.view = "/AirPhoto/.view/" + name + ".bmp";
  result.landscapeView = "/AirPhoto/.view/" + name + ".land.bmp";
  result.thumb = "/AirPhoto/.thumb/" + name + ".bmp";
  return result;
}

}  // namespace airphoto
