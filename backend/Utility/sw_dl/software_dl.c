#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <curl/curl.h>
#include <unistd.h>
#include <json-c/json.h>

#define BUFFER_SIZE 1024
#define SW_VER "/var/tmp/sw_version.txt"
#define CONFIG_FILE_PATH "/home/rats/RATS/Backend/Utility/sw_dl/repourl.txt"

// Struct to hold data received from GitHub API
struct MemoryStruct {
	char *memory;
	size_t size;
};

bool check_environment() {
	//return 1 for Prod and 0 for Dev
	const char* flag_file = "/var/tmp/dev_environment.txt";
	return (access(flag_file, F_OK) == -1);
}

// check if dev_environment.txt flag available
bool is_environment_prod = true;

// Function to execute a command and capture its output
char* execute_command(const char* command) {
	FILE* fp = popen(command, "r");
	if (!fp) {
		perror("Failed to execute command");
		exit(EXIT_FAILURE);
	}

	char buffer[1024];
	char* result = NULL;
	while (fgets(buffer, sizeof(buffer), fp) != NULL) {
		result = strdup(buffer);
	}
	pclose(fp);
	return result;
}

// Function to read variables from repourl.txt
void read_config(char *repo_url, char *url_release_check) {
	FILE *file = fopen(CONFIG_FILE_PATH, "r");
	if (!file) {
		perror("Failed to open utility.txt");
		exit(EXIT_FAILURE);
	}

	char line[BUFFER_SIZE];
	while (fgets(line, sizeof(line), file)) {
		if(is_environment_prod){
			if (strncmp(line, "REPO_URL=", 9) == 0) {
				strcpy(repo_url, line + 9);
				repo_url[strcspn(repo_url, "\n")] = 0; // Remove newline
			} else if (strncmp(line, "URL_RELEASE_CHECK=", 18) == 0) {
				strcpy(url_release_check, line + 18);
				url_release_check[strcspn(url_release_check, "\n")] = 0; // Remove newline
			}
		} else {
			if (strncmp(line, "DEV_REPO_URL=",13) == 0) {
				strcpy(repo_url, line + 13);
				repo_url[strcspn(repo_url, "\n")] = 0; // Remove newline
			} else if (strncmp(line, "DEV_URL_RELEASE_CHECK=", 22) == 0) {
				strcpy(url_release_check, line + 22);
				url_release_check[strcspn(url_release_check, "\n")] = 0; // Remove newline
			}
		}
	}

	fclose(file);
}

// Callback function to handle received data from GitHub API
static size_t WriteMemoryCallback(void *contents, size_t size, size_t nmemb, void *userp) {
	size_t realsize = size * nmemb;
	struct MemoryStruct *mem = (struct MemoryStruct *)userp;

	mem->memory = realloc(mem->memory, mem->size + realsize + 1);
	if (mem->memory == NULL) {
		printf("not enough memory (realloc returned NULL)\n");
		return 0;
	}

	memcpy(&(mem->memory[mem->size]), contents, realsize);
	mem->size += realsize;
	mem->memory[mem->size] = 0;

	return realsize;
}

// Function to extract the tag name from the JSON response using cJSON
char *extract_tag_name(const char *json_data) {
	struct json_object *root = json_tokener_parse(json_data);
	if (!root) {
		fprintf(stderr, "Error: Failed to parse JSON\n");
		return NULL;
	}

	struct json_object *tag_name_json = json_object_object_get(root, "tag_name");
	if (!tag_name_json) {
		fprintf(stderr, "Error: tag_name not found\n");
		json_object_put(root);
		return NULL;
	}

	const char *tag_name = json_object_get_string(tag_name_json);
	char *tag_name_copy = strdup(tag_name);

	json_object_put(root);

	return tag_name_copy;
}

// Function to check latest version from GitHub
char *check_latest_version(const char *url_release_check, const char *repo_url) {
	CURL *curl_handle;
	CURLcode res;
	struct MemoryStruct chunk;
	char username[256] = {0};  // Buffer for storing the username
	char token[256] = {0};	 // Buffer for storing the token
	get_git_config(username, token);

	chunk.memory = malloc(1);  // will be grown as needed by realloc
	chunk.size = 0;			 // no data at this point

	if(is_environment_prod) {
		curl_global_init(CURL_GLOBAL_ALL);
		curl_handle = curl_easy_init();
		if (curl_handle) {
			curl_easy_setopt(curl_handle, CURLOPT_URL, url_release_check);
			curl_easy_setopt(curl_handle, CURLOPT_WRITEFUNCTION, WriteMemoryCallback);
			curl_easy_setopt(curl_handle, CURLOPT_WRITEDATA, (void *)&chunk);

			// Set Authorization header with token value
			struct curl_slist *headers = NULL;
			char auth_header[64];
			sprintf(auth_header, "Authorization: token %s", token);
			headers = curl_slist_append(headers, auth_header);
			curl_easy_setopt(curl_handle, CURLOPT_HTTPHEADER, headers);

			// Add User-Agent header
			curl_easy_setopt(curl_handle, CURLOPT_USERAGENT, "YourUserAgent");

			res = curl_easy_perform(curl_handle);
			if (res != CURLE_OK) {
				fprintf(stderr, "curl_easy_perform() failed: %s\n", curl_easy_strerror(res));
			}

			// Clean up
			curl_easy_cleanup(curl_handle);
			curl_slist_free_all(headers);
		}
		curl_global_cleanup();
		return chunk.memory;
	} else {
		char command[512];
		sprintf(command, "git ls-remote https://%s:%s@%s HEAD | awk '{print substr($1,1,7)}'", username, token, repo_url);
		char* output = execute_command(command);
		output[strcspn(output, "\r\n")] = '\0';
		size_t len = strlen(output);
		char* short_commit_id = (char*)malloc(len + 1);
		memcpy(short_commit_id, output, len + 1);
		free(output);
		return short_commit_id;
	}
}

void get_git_config(char *username, char *token) {
	FILE *fp;
	char output[1035];

	// Open the command for reading
	fp = popen("git config --list", "r");
	if (fp == NULL) {
		printf("Failed to run command\n");
		exit(1);
	}

	// Read the output a line at a time - output it
	while (fgets(output, sizeof(output), fp) != NULL) {
		// Check if the line contains 'user.name'
		if (strncmp(output, "user.name=", 10) == 0) {
			strncpy(username, output + 10, strlen(output) - 10 - 1); // -1 to remove the newline character
		}
		// Check if the line contains 'section.key'
		else if (strncmp(output, "section.key=", 12) == 0) {
			strncpy(token, output + 12, strlen(output) - 12 - 1); // -1 to remove the newline character
		}
	}

	// Close the pipe
	pclose(fp);
}

void check_and_upgrade(const char *current_version, const char *repo_url, const char *url_release_check, const char *commit_id) {
	char username[256] = {0};  // Buffer for storing the username
	char token[256] = {0};	 // Buffer for storing the token
	get_git_config(username, token);
	printf("get_git_config username: %s\n", username);
	printf("get_git_config token: %s\n", token);
	char *latest_version_json = check_latest_version(url_release_check, repo_url);

	if (latest_version_json) {
		printf("Latest version JSON: %s\n", latest_version_json);

		if(is_environment_prod) {
			// Extract tag name from JSON
			char *tag_name = extract_tag_name(latest_version_json);
			if (tag_name) {
				printf("Latest version tag: %s\n", tag_name);
				if (strcmp(tag_name, current_version) != 0) {
					printf("A newer version (%s) is available. Updating...\n", tag_name);

					char command[512];
					sprintf(command, "cd ../../../../ && git clone -b release https://%s:%s@%s RATS-%s && cd RATS-%s && git checkout tags/%s ", username, token, repo_url, tag_name, tag_name, tag_name);
					int result = system(command);
					if (result != 0) {
						printf("Failed to update the repository.\n");
					} else {
						memset(command, 0, sizeof(command));
						sprintf(command, "echo RATS-%s > %s\n", tag_name, SW_VER);
						system(command);
						printf("Upgrade downloaded.\n");
						const char *command1 = "(crontab -l 2>/dev/null; echo \"*/1 * * * * sh /home/rats/RATS/Backend/Utility/sw_dl/software_migration.sh\") | crontab -";
						system(command1);

						printf("Migrating to new software...\n");
					}
				} else {
					printf("You are already using the latest version.\n");
				}
				free(tag_name);
			} else {
				printf("Failed to extract tag name from JSON.\n");
			}
		} else {
			char short_id[8] = {0}; // 7 chars + '\0'
			printf("Latest Commit ID: %s\n", latest_version_json);
			printf("Received Commit ID: %s\n", commit_id);
			strcpy(short_id, latest_version_json);
			if (commit_id[0] != '\0') {
				if (strlen(commit_id) > 7) {
					strncpy(short_id, commit_id, 7);
					short_id[7] = '\0';
				}
				else strcpy(short_id, commit_id);
				printf("Updating to Commit ID: %s\n", commit_id);
			}
			free(latest_version_json);
			if (strcmp(short_id, current_version) != 0) {
				printf("A newer version (%s) is available. Updating...\n", short_id);

				char command[512];
				sprintf(command, "cd ../../../../ && git clone https://%s:%s@%s RATS-%s && cd RATS-%s && git checkout %s ", username, token, repo_url, short_id, short_id, short_id);
				printf("Cloning using command:%s\n", command);
				int result = system(command);
				if (result != 0) {
					printf("Failed to update the repository.\n");
				} else {
					memset(command, 0, sizeof(command));
					sprintf(command, "echo RATS-%s > %s\n", short_id, SW_VER);
					system(command);
					printf("Upgrade downloaded.\n");
					const char *command1 = "(crontab -l 2>/dev/null; echo \"*/1 * * * * sh /home/rats/RATS/Backend/Utility/sw_dl/software_migration.sh\") | crontab -";
					system(command1);

					printf("Migrating to new software...\n");
				}
			}
		}
	} else {
		printf("Failed to retrieve the latest version information.\n");
	}
}

// Function to get the current release name from a cloned Git repository
char* get_current_release_name() {
	char* release_name = NULL;
	if(is_environment_prod) {
		// Execute 'git describe --tags' command to get the current release name
		release_name = execute_command("git describe --tags");
	} else {
		// Execute 'git rev-parse --short HEAD' command to get the current Commit ID
		release_name = execute_command("git rev-parse --short HEAD");
	}
	// Strip newline character if present
	release_name[strcspn(release_name, "\r\n")] = '\0';
	return release_name;
}

int main(int argc, char *argv[]) {
	// check if dev_environment.txt flag available
	is_environment_prod = check_environment();
	printf("environment: %s\n", ((is_environment_prod)?"Prod":"Dev"));

	char commit_id[BUFFER_SIZE] = {0};
	if (argc >= 2) {
		strncpy(commit_id, argv[1], sizeof(commit_id) - 1);
		commit_id[sizeof(commit_id) - 1] = '\0';
	}
	printf("commit_id: %s\n", commit_id);
	char repo_url[BUFFER_SIZE] = {0};
	char url_release_check[BUFFER_SIZE] = {0};

	// Read configuration from utility.txt
	read_config(repo_url, url_release_check);
	printf("Current repo_url: %s\n", repo_url);
	printf("Current url_release_check: %s\n", url_release_check);

	const char *current_version = get_current_release_name();
	printf("Current version: %s\n", current_version);
	check_and_upgrade(current_version, repo_url, url_release_check, commit_id);
	free(current_version);

	return 0;
}
